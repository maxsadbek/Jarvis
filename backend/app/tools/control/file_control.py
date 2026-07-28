"""File Control Module (Enhanced).

Advanced file operations:
- Create files and folders
- Search files by name/pattern
- Move/copy/rename
- Organize by type
- Get file information
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from backend.app.tools.base import BaseTool
from backend.app.models.schemas import RiskLevel


class FileControlTool(BaseTool):
    """Create, search, move, organize files on the filesystem."""

    def __init__(self) -> None:
        super().__init__()
        self._risk_level = RiskLevel.LOW
        self._allowed_base = Path.cwd()
        self._parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "create",
                        "delete",
                        "move",
                        "copy",
                        "rename",
                        "search",
                        "info",
                        "organize",
                        "read",
                        "write",
                    ],
                    "description": "File action to perform",
                },
                "path": {
                    "type": "string",
                    "description": "File or folder path",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (for move/copy/rename)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for create/write)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (glob, e.g., '*.py')",
                },
                "type": {
                    "type": "string",
                    "enum": ["file", "folder", "auto"],
                    "description": "Type for create action",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        return "file_control"

    @property
    def description(self) -> str:
        return "Create, read, write, search, move, copy, organize files and folders"

    def _resolve(self, path_str: str) -> Path:
        """Resolve path relative to allowed base, preventing traversal."""
        p = Path(path_str)
        if not p.is_absolute():
            p = self._allowed_base / p
        p = p.resolve()
        # Security check
        try:
            p.relative_to(self._allowed_base)
        except ValueError:
            # Check common safe paths
            safe_paths = [
                Path.home() / "Desktop",
                Path.home() / "Documents",
                Path.home() / "Downloads",
            ]
            for safe in safe_paths:
                try:
                    p.relative_to(safe)
                    return p
                except ValueError:
                    continue
            raise PermissionError(f"Path '{path_str}' is not allowed")
        return p

    async def execute(self, action: str, path: str = "", destination: str = "",
                      content: str = "", pattern: str = "", type: str = "auto",
                      **kwargs: Any) -> dict[str, Any]:
        handlers = {
            "create": self._create,
            "delete": self._delete,
            "move": self._move,
            "copy": self._copy,
            "rename": self._rename,
            "search": self._search,
            "info": self._info,
            "organize": self._organize,
            "read": self._read,
            "write": self._write,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown action: {action}", "result": ""}

        return await handler(path=path, destination=destination, content=content, pattern=pattern, file_type=type)

    async def _create(self, path: str = "", destination: str = "", content: str = "",
                      pattern: str = "", file_type: str = "auto") -> dict[str, Any]:
        """Create a file or folder."""
        if not path:
            return {"success": False, "error": "Path required", "result": ""}

        try:
            resolved = self._resolve(path)
            # Determine type
            if file_type == "folder" or (file_type == "auto" and not resolved.suffix):
                resolved.mkdir(parents=True, exist_ok=True)
                return {"success": True, "result": f"Created folder: {resolved.name}"}
            else:
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(content or "", encoding="utf-8")
                return {"success": True, "result": f"Created file: {resolved.name} ({len(content)} bytes)"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _delete(self, path: str = "", destination: str = "", content: str = "",
                      pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Delete a file or empty folder."""
        if not path:
            return {"success": False, "error": "Path required", "result": ""}
        try:
            resolved = self._resolve(path)
            if not resolved.exists():
                return {"success": False, "error": f"Not found: {path}", "result": ""}
            if resolved.is_dir():
                resolved.rmdir() if not any(resolved.iterdir()) else shutil.rmtree(resolved)
                return {"success": True, "result": f"Deleted folder: {resolved.name}"}
            else:
                resolved.unlink()
                return {"success": True, "result": f"Deleted file: {resolved.name}"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _move(self, path: str = "", destination: str = "", content: str = "",
                    pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Move a file or folder."""
        if not path or not destination:
            return {"success": False, "error": "Source and destination required", "result": ""}
        try:
            src = self._resolve(path)
            dst = self._resolve(destination)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {"success": True, "result": f"Moved to: {destination}"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _copy(self, path: str = "", destination: str = "", content: str = "",
                    pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Copy a file or folder."""
        if not path or not destination:
            return {"success": False, "error": "Source and destination required", "result": ""}
        try:
            src = self._resolve(path)
            dst = self._resolve(destination)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            return {"success": True, "result": f"Copied to: {destination}"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _rename(self, path: str = "", destination: str = "", content: str = "",
                      pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Rename a file or folder."""
        if not path or not destination:
            return {"success": False, "error": "Current and new name required", "result": ""}
        try:
            src = self._resolve(path)
            dst = src.parent / destination
            src.rename(dst)
            return {"success": True, "result": f"Renamed to: {destination}"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _search(self, path: str = "", destination: str = "", content: str = "",
                      pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Search for files by glob pattern."""
        search_path = self._resolve(path) if path else self._allowed_base
        pattern = pattern or "*"
        try:
            matches = list(search_path.rglob(pattern))
            if not matches:
                return {"success": True, "result": f"No files matching '{pattern}'", "count": 0}

            result_lines = [f"Found {len(matches)} files matching '{pattern}':"]
            for m in matches[:50]:
                rel = m.relative_to(self._allowed_base) if m.is_relative_to else m
                result_lines.append(f"  {'📁' if m.is_dir() else '📄'} {rel}")
            if len(matches) > 50:
                result_lines.append(f"  ... and {len(matches) - 50} more")

            return {"success": True, "result": "\n".join(result_lines), "count": len(matches)}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _info(self, path: str = "", destination: str = "", content: str = "",
                    pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Get file/directory information."""
        if not path:
            return {"success": False, "error": "Path required", "result": ""}
        try:
            import time as tmod
            resolved = self._resolve(path)
            if not resolved.exists():
                return {"success": False, "error": f"Not found: {path}", "result": ""}
            stat = resolved.stat()
            info = (
                f"Name: {resolved.name}\n"
                f"Path: {resolved}\n"
                f"Type: {'Directory' if resolved.is_dir() else 'File'}\n"
                f"Size: {_format_size(stat.st_size)}\n"
                f"Created: {tmod.ctime(stat.st_ctime)}\n"
                f"Modified: {tmod.ctime(stat.st_mtime)}"
            )
            return {"success": True, "result": info}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _read(self, path: str = "", destination: str = "", content: str = "",
                    pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Read file contents."""
        if not path:
            return {"success": False, "error": "Path required", "result": ""}
        try:
            resolved = self._resolve(path)
            if not resolved.exists() or not resolved.is_file():
                return {"success": False, "error": f"File not found: {path}", "result": ""}
            text = resolved.read_text(encoding="utf-8", errors="replace")
            if len(text) > 100_000:
                text = text[:100_000] + "\n... [truncated]"
            return {"success": True, "result": text, "size_bytes": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _write(self, path: str = "", destination: str = "", content: str = "",
                     pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Write content to a file (create or overwrite)."""
        if not path:
            return {"success": False, "error": "Path required", "result": ""}
        try:
            resolved = self._resolve(path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content or "", encoding="utf-8")
            return {"success": True, "result": f"Written {len(content or '')} bytes to {resolved.name}"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _organize(self, path: str = "", destination: str = "", content: str = "",
                        pattern: str = "", file_type: str = "") -> dict[str, Any]:
        """Organize files in a directory by type/extension."""
        base_path = self._resolve(path) if path else self._allowed_base
        if not base_path.is_dir():
            return {"success": False, "error": f"Not a directory: {path}", "result": ""}

        try:
            organized = 0
            categories = {
                "Images": [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico"],
                "Documents": [".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"],
                "Code": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".yaml", ".yml", ".toml"],
                "Data": [".csv", ".xml", ".xlsx", ".xls", ".db", ".sqlite", ".sql"],
                "Archives": [".zip", ".tar", ".gz", ".rar", ".7z"],
                "Audio": [".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma"],
                "Video": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"],
                "Executables": [".exe", ".msi", ".bat", ".ps1", ".cmd"],
            }

            for item in base_path.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    ext = item.suffix.lower()
                    for category, extensions in categories.items():
                        if ext in extensions:
                            cat_dir = base_path / category
                            cat_dir.mkdir(exist_ok=True)
                            dest = cat_dir / item.name
                            if not dest.exists():
                                shutil.move(str(item), str(dest))
                                organized += 1
                            break

            return {"success": True, "result": f"Organized {organized} files into folders"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}


def _format_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
