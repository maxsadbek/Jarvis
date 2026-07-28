"""File Operations Tool.

Allows JARVIS to read, write, and manage files.
Includes security checks for allowed directories and file types.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.tools.base import BaseTool


class FileOpsTool(BaseTool):
    """Read, write, and manage files on the system."""

    def __init__(self) -> None:
        super().__init__()
        self._allowed_base = Path.cwd()
        self._parameters = {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete", "info", "search"],
                    "description": "File operation to perform",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path (relative or absolute)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write operation)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (for search operation)",
                },
            },
            "required": ["operation", "path"],
        }

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return "Read, write, list, search, and manage files on the computer"

    SAFE_FILE_EXTENSIONS: set = {".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
                                 ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
                                 ".csv", ".xml", ".html", ".css", ".scss"}

    MAX_OUTPUT_SIZE: int = 100_000

    def _resolve_path(self, path: str) -> Optional[Path]:
        """Resolve a path safely, preventing directory traversal and symlink attacks."""
        try:
            p = Path(path)
            if not p.is_absolute():
                p = self._allowed_base / p
            p = p.resolve(strict=False)

            # Security: Ensure resolved path is within allowed directories
            try:
                p.relative_to(self._allowed_base)
            except ValueError:
                logger.warning(f"Path traversal blocked: {path} -> {p}")
                return None

            return p
        except (OSError, ValueError, RuntimeError):
            return None

    async def execute(self, operation: str, path: str, content: str = "", pattern: str = "", **kwargs: Any) -> dict[str, Any]:
        """Execute a file operation."""
        resolved = self._resolve_path(path)
        if not resolved:
            return {
                "success": False,
                "error": f"Access denied: path '{path}' is outside allowed directories",
                "result": "",
            }

        operations = {
            "read": self._read_file,
            "write": self._write_file,
            "list": self._list_directory,
            "delete": self._delete_file,
            "info": self._file_info,
            "search": self._search_files,
        }

        handler = operations.get(operation)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "result": "",
            }

        return await handler(resolved, content, pattern)

    async def _read_file(self, path: Path, content: str = "", pattern: str = "") -> dict[str, Any]:
        """Read a file's contents."""
        try:
            if not path.exists():
                return {"success": False, "error": f"File not found: {path}", "result": ""}

            if not path.is_file():
                return {"success": False, "error": f"Not a file: {path}", "result": ""}

            # Check file size
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > settings.MAX_FILE_SIZE_MB:
                return {"success": False, "error": f"File too large ({size_mb:.1f} MB)", "result": ""}

            # Check extension
            ext = path.suffix.lower()
            if ext not in settings.ALLOWED_FILE_EXTENSIONS:
                return {"success": False, "error": f"File type not allowed: {ext}", "result": ""}

            if ext in self.SAFE_FILE_EXTENSIONS:
                content = path.read_text(encoding="utf-8", errors="replace")
                # Truncate if too long
                if len(content) > self.MAX_OUTPUT_SIZE:
                    content = content[:self.MAX_OUTPUT_SIZE] + "\n\n... [truncated]"
                return {"success": True, "result": content, "size_bytes": len(content)}
            else:
                return {"success": True, "result": f"[Binary file: {path.name}, {path.stat().st_size} bytes]"}

        except Exception as e:
            return {"success": False, "error": f"Read failed: {str(e)}", "result": ""}

    async def _write_file(self, path: Path, content: str = "", pattern: str = "") -> dict[str, Any]:
        """Write content to a file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"success": True, "result": f"Written {len(content)} bytes to {path.name}"}
        except Exception as e:
            return {"success": False, "error": f"Write failed: {str(e)}", "result": ""}

    async def _list_directory(self, path: Path, content: str = "", pattern: str = "") -> dict[str, Any]:
        """List directory contents."""
        try:
            if not path.exists():
                return {"success": False, "error": f"Directory not found: {path}", "result": ""}

            if not path.is_dir():
                return {"success": False, "error": f"Not a directory: {path}", "result": ""}

            entries = []
            for entry in sorted(path.iterdir()):
                entry_type = "📁" if entry.is_dir() else "📄"
                size = entry.stat().st_size if entry.is_file() else 0
                entries.append(f"{entry_type} {entry.name} ({_format_size(size)})")

            result = f"Contents of {path}:\n" + "\n".join(entries) if entries else "(empty directory)"
            return {"success": True, "result": result, "items": len(entries)}

        except Exception as e:
            return {"success": False, "error": f"List failed: {str(e)}", "result": ""}

    async def _delete_file(self, path: Path, content: str = "", pattern: str = "") -> dict[str, Any]:
        """Delete a file (not directories)."""
        try:
            if not path.exists():
                return {"success": False, "error": f"Not found: {path}", "result": ""}

            if path.is_dir():
                return {"success": False, "error": "Cannot delete directories with this tool", "result": ""}

            path.unlink()
            return {"success": True, "result": f"Deleted: {path.name}"}

        except Exception as e:
            return {"success": False, "error": f"Delete failed: {str(e)}", "result": ""}

    async def _file_info(self, path: Path, content: str = "", pattern: str = "") -> dict[str, Any]:
        """Get file/directory information."""
        try:
            if not path.exists():
                return {"success": False, "error": f"Not found: {path}", "result": ""}

            import time
            stat = path.stat()
            info = (
                f"Name: {path.name}\n"
                f"Path: {path}\n"
                f"Type: {'Directory' if path.is_dir() else 'File'}\n"
                f"Size: {_format_size(stat.st_size)}\n"
                f"Created: {time.ctime(stat.st_ctime)}\n"
                f"Modified: {time.ctime(stat.st_mtime)}\n"
                f"Permissions: {oct(stat.st_mode)[-3:]}"
            )
            return {"success": True, "result": info}

        except Exception as e:
            return {"success": False, "error": f"Info failed: {str(e)}", "result": ""}

    async def _search_files(self, path: Path, content: str = "", pattern: str = "") -> dict[str, Any]:
        """Search for files matching a pattern."""
        try:
            if not path.is_dir():
                return {"success": False, "error": "Path must be a directory for search", "result": ""}

            if not pattern:
                return {"success": False, "error": "Search pattern required", "result": ""}

            matches = []
            for p in path.rglob(pattern):
                matches.append(str(p.relative_to(self._allowed_base)))

            if matches:
                result = f"Found {len(matches)} matches:\n" + "\n".join(matches[:50])
                if len(matches) > 50:
                    result += f"\n... and {len(matches) - 50} more"
            else:
                result = f"No files matching '{pattern}'"

            return {"success": True, "result": result, "matches": len(matches)}

        except Exception as e:
            return {"success": False, "error": f"Search failed: {str(e)}", "result": ""}


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
