"""Command Runner Tool.

Executes approved system commands through the CommandSandbox.
Includes comprehensive security validation and audit logging.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.app.tools.base import BaseTool
from backend.app.tools.executor import CommandSandbox


class CommandRunnerTool(BaseTool):
    """Run approved system commands safely."""

    def __init__(self) -> None:
        super().__init__()
        self._sandbox = CommandSandbox()
        self._parameters = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (max 60)",
                    "default": 30,
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory (must be allowed)",
                },
            },
            "required": ["command"],
        }

    @property
    def name(self) -> str:
        return "command_runner"

    @property
    def description(self) -> str:
        return "Run approved system commands safely with security sandbox"

    async def execute(
        self,
        command: str,
        timeout: int = 30,
        working_dir: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a command through the security sandbox.

        Args:
            command: Command string to execute.
            timeout: Timeout in seconds (max 60).
            working_dir: Working directory override.

        Returns:
            Dict with execution results.
        """
        # Enforce max timeout
        actual_timeout = min(timeout, 60)

        result = await self._sandbox.execute(
            command=command,
            timeout=actual_timeout,
            working_dir=working_dir or None,
        )

        if result.get("success"):
            output = result.get("stdout", "")
            if result.get("stderr"):
                output += f"\n[Stderr]: {result['stderr']}"
            return {
                "success": True,
                "result": output.strip() or "(no output)",
                "returncode": result.get("returncode"),
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Command failed"),
                "result": result.get("stdout", ""),
                "returncode": result.get("returncode"),
            }
