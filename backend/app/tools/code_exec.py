"""Code Execution Tool.

Safely executes code snippets (Python, JavaScript, etc.)
in isolated subprocesses with timeout and resource limits.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.tools.base import BaseTool
from backend.app.tools.executor import CommandSandbox


class CodeExecutionTool(BaseTool):
    """Execute code snippets safely in isolated subprocesses."""

    def __init__(self) -> None:
        super().__init__()
        self._sandbox = CommandSandbox()
        self._parameters = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code to execute",
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "python3", "node", "javascript", "shell", "powershell"],
                    "description": "Programming language",
                    "default": "python",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (max 30)",
                    "default": 15,
                },
                "description": {
                    "type": "string",
                    "description": "What this code does (for audit log)",
                    "default": "",
                },
            },
            "required": ["code"],
        }

    @property
    def name(self) -> str:
        return "code_exec"

    @property
    def description(self) -> str:
        return "Execute code snippets in Python, JavaScript, shell, or PowerShell"

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 15,
        description: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a code snippet safely.

        Args:
            code: Code to execute.
            language: Language runtime to use.
            timeout: Timeout in seconds (max 30).
            description: What the code does.

        Returns:
            Dict with execution results.
        """
        actual_timeout = min(timeout, 30)

        # Validate code for dangerous patterns
        is_valid, reason = self._validate_code(code, language)
        if not is_valid:
            return {"success": False, "error": reason, "result": ""}

        # Write code to temporary file
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=self._get_extension(language),
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(code)
                temp_path = f.name

            # Build execution command
            command = self._build_command(temp_path, language)

            logger.info(f"Executing {language} code: {description or code[:60]}...")

            result = await self._sandbox.execute(
                command=command,
                timeout=actual_timeout,
            )

            return result

        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return {"success": False, "error": str(e), "result": ""}
        finally:
            # Clean up temp file
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _validate_code(self, code: str, language: str) -> tuple[bool, str]:
        """Validate code for dangerous patterns.

        Args:
            code: Code to validate.
            language: Language runtime.

        Returns:
            Tuple of (is_valid, reason).
        """
        if not code or not code.strip():
            return False, "Empty code"

        if len(code) > 100_000:
            return False, "Code too long (max 100K chars)"

        # Block dangerous imports/operations (after normalizing whitespace)
        import re as _re
        code_lower = code.lower()
        normalized_code = _re.sub(r'\s+', ' ', code_lower)

        dangerous_patterns = {
            "python": [
                "import os", "from os import", "os.system", "os.popen",
                "subprocess", "shutil.rmtree", "pathlib.Path.unlink",
                "__import__", "eval(", "exec(", "compile(",
                "open(", "file(", "with open",
                "import shutil", "import pathlib",
            ],
            "node": [
                "require('child_process')", "require('fs')",
                "process.exit", "exec(", "eval(",
                "require('net')", "require('dgram')",
                "require('http')", "require('https')",
            ],
        }

        patterns = dangerous_patterns.get(language, [])
        for pattern in patterns:
            if pattern.lower() in normalized_code:
                return False, f"Dangerous pattern detected: '{pattern}'"

        return True, ""

    def _get_extension(self, language: str) -> str:
        """Get file extension for a language."""
        extensions = {
            "python": ".py",
            "python3": ".py",
            "node": ".js",
            "javascript": ".js",
            "shell": ".sh",
            "powershell": ".ps1",
        }
        return extensions.get(language, ".txt")

    def _build_command(self, file_path: str, language: str) -> str:
        """Build the command to execute code.

        Args:
            file_path: Path to the temp file.
            language: Language runtime.

        Returns:
            Command string.
        """
        commands = {
            "python": f"python \"{file_path}\"",
            "python3": f"python3 \"{file_path}\"",
            "node": f"node \"{file_path}\"",
            "javascript": f"node \"{file_path}\"",
            "shell": f"bash \"{file_path}\"",
            "powershell": f"powershell -File \"{file_path}\"",
        }
        return commands.get(language, f"python \"{file_path}\"")
