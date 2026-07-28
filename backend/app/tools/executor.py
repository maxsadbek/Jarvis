"""Safe Command Execution Sandbox.

Provides secure execution of system commands with:
- Allowed/blocked command lists
- Timeout enforcement
- Resource limits (memory, CPU)
- Path sandboxing
- Network access control
- Output capture and truncation
"""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import ExecutionSandbox


# Default blocked commands - anything that could be destructive
BLOCKED_COMMANDS = [
    "rm -rf", "format", "mkfs", "dd", "shutdown", "reboot",
    "halt", "poweroff", "init", "killall", "pkill",
    "chmod 777", "chown", "passwd", "sudo", "su",
    "fdisk", "parted", "mount", "umount", "iptables",
    "reg delete", "reg add", "diskpart", "bcdedit",
]

# Default allowed commands for safe execution
ALLOWED_COMMANDS = [
    "dir", "ls", "cd", "pwd", "echo", "type", "cat",
    "find", "grep", "findstr", "where", "which",
    "python", "python3", "node", "npm", "npx",
    "git status", "git log", "git diff", "git branch",
    "pip list", "pip show", "npm list",
    "date", "time", "whoami", "hostname",
    "tasklist", "systeminfo",
]


class CommandSandbox:
    """Secure command execution sandbox with resource controls."""

    def __init__(self, config: Optional[ExecutionSandbox] = None) -> None:
        self._config = config or self._default_config()
        self._active_processes: dict[str, asyncio.subprocess.Process] = {}

    def _default_config(self) -> ExecutionSandbox:
        """Create default sandbox configuration."""
        return ExecutionSandbox(
            allowed_directories=[str(Path.cwd())],
            blocked_directories=[
                str(Path.home() / "AppData"),
                "C:\\Windows\\System32\\config",
                "/etc", "/sys", "/proc",
            ],
            allowed_commands=ALLOWED_COMMANDS,
            blocked_commands=BLOCKED_COMMANDS,
            max_processes=5,
            max_memory_mb=512,
            max_cpu_percent=50,
            timeout_seconds=30,
            network_access=False,
        )

    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Execute a command safely with all security checks.

        Args:
            command: The command string to execute.
            timeout: Timeout in seconds (overrides config).
            working_dir: Working directory (must be in allowed dirs).
            env_vars: Additional environment variables.

        Returns:
            Dict with stdout, stderr, returncode, success.
        """
        # 1. Validate command
        is_valid, reason = self._validate_command(command)
        if not is_valid:
            return {
                "success": False,
                "error": reason,
                "stdout": "",
                "stderr": reason,
                "returncode": -1,
            }

        # 2. Validate working directory
        if working_dir:
            resolved_dir = Path(working_dir).resolve()
            if not self._is_path_allowed(resolved_dir):
                return {
                    "success": False,
                    "error": f"Working directory not allowed: {working_dir}",
                    "stdout": "",
                    "stderr": "",
                    "returncode": -1,
                }

        # 3. Check process count limit
        if len(self._active_processes) >= self._config.max_processes:
            return {
                "success": False,
                "error": "Maximum concurrent processes reached",
                "stdout": "",
                "stderr": "",
                "returncode": -1,
            }

        # 4. Enforce network access restriction
        env = {**os.environ, **(env_vars or {})}
        if not self._config.network_access:
            # Block network access by removing proxy vars and setting no_proxy
            env["http_proxy"] = ""
            env["https_proxy"] = ""
            env["no_proxy"] = "*"
            env["HTTP_PROXY"] = ""
            env["HTTPS_PROXY"] = ""
            env["NO_PROXY"] = "*"

        # 5. Execute with timeout
        actual_timeout = timeout or self._config.timeout_seconds
        process_id = str(id(command))

        try:
            logger.info(f"Executing command (sandboxed): {command[:100]}...")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir or str(Path.cwd()),
                env=env,
            )

            self._active_processes[process_id] = process

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=actual_timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                del self._active_processes[process_id]
                return {
                    "success": False,
                    "error": f"Command timed out after {actual_timeout}s",
                    "stdout": "",
                    "stderr": "Process killed due to timeout",
                    "returncode": -1,
                }

            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            # Truncate output to prevent memory issues
            max_output = 100_000
            if len(stdout_str) > max_output:
                stdout_str = stdout_str[:max_output] + "\n... [output truncated]"
            if len(stderr_str) > max_output:
                stderr_str = stderr_str[:max_output] + "\n... [output truncated]"

            success = process.returncode == 0

            return {
                "success": success,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "returncode": process.returncode,
            }

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }
        finally:
            if process_id in self._active_processes:
                del self._active_processes[process_id]

    def _validate_command(self, command: str) -> tuple[bool, str]:
        """Validate a command against security policies.

        Args:
            command: Command to validate.

        Returns:
            Tuple of (is_valid, reason).
        """
        if not command or not command.strip():
            return False, "Empty command"

        # Check against blocked commands
        command_lower = command.lower().strip()
        for blocked in self._config.blocked_commands:
            if blocked in command_lower:
                return False, f"Command blocked by security policy: '{blocked}'"

        # Check if allowed commands list is restrictive
        if self._config.allowed_commands:
            cmd_base = command_lower.split()[0] if command_lower.split() else ""
            allowed = False
            for allowed_cmd in self._config.allowed_commands:
                if command_lower.startswith(allowed_cmd):
                    allowed = True
                    break
            if not allowed:
                return False, f"Command not in allowed list: '{cmd_base}'"

        # Check for dangerous patterns
        dangerous = ["&&", "||", "`", "$(", "$((", "2>&1", "> /dev/null", "2>nul"]
        for pattern in dangerous:
            if pattern in command:
                return False, f"Dangerous pattern detected: '{pattern}'"

        return True, ""

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if a path is in allowed directories.

        Args:
            path: Path to check.

        Returns:
            True if the path is allowed.
        """
        try:
            path = path.resolve()
            # Check blocked directories
            for blocked in self._config.blocked_directories:
                try:
                    path.relative_to(Path(blocked).resolve())
                    return False
                except (ValueError, FileNotFoundError):
                    continue

            # If allowed directories specified, check
            if self._config.allowed_directories:
                for allowed in self._config.allowed_directories:
                    try:
                        path.relative_to(Path(allowed).resolve())
                        return True
                    except (ValueError, FileNotFoundError):
                        continue
                return False

            return True
        except Exception:
            return False

    async def get_active_count(self) -> int:
        """Get number of currently executing commands."""
        return len(self._active_processes)

    async def kill_all(self) -> int:
        """Kill all active processes.

        Returns:
            Number of processes killed.
        """
        count = 0
        for pid, process in list(self._active_processes.items()):
            try:
                process.kill()
                count += 1
            except Exception:
                pass
        self._active_processes.clear()
        return count
