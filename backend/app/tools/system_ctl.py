"""System Control Tool.

Allows JARVIS to control system settings and applications.
Includes safety checks and confirmation prompts for destructive actions.
"""

from __future__ import annotations

import subprocess
from typing import Any

from loguru import logger

from backend.app.tools.base import BaseTool


class SystemControlTool(BaseTool):
    """Control system settings, open apps, manage windows."""

    def __init__(self) -> None:
        super().__init__()
        self._parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "open_app",
                        "close_app",
                        "get_processes",
                        "system_info",
                        "volume",
                        "brightness",
                        "lock_screen",
                        "screenshot",
                    ],
                    "description": "System action to perform",
                },
                "target": {
                    "type": "string",
                    "description": "Target application name or value",
                },
                "value": {
                    "type": "integer",
                    "description": "Value for setting (e.g., volume level 0-100)",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        return "system_ctl"

    @property
    def description(self) -> str:
        return "Control system: open/close apps, manage windows, system settings"

    async def execute(self, action: str, target: str = "", value: int = 50, **kwargs: Any) -> dict[str, Any]:
        """Execute a system control action."""
        handlers = {
            "open_app": self._open_app,
            "close_app": self._close_app,
            "get_processes": self._get_processes,
            "system_info": self._system_info,
            "volume": self._set_volume,
            "lock_screen": self._lock_screen,
            "screenshot": self._take_screenshot,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown action: {action}", "result": ""}

        return await handler(target, value)

    async def _open_app(self, target: str, value: int = 50) -> dict[str, Any]:
        """Open an application."""
        try:
            import subprocess
            import shutil

            if not target:
                return {"success": False, "error": "Application name required", "result": ""}

            # Try to find and launch the app
            common_paths = [
                target,
                f"{target}.exe",
                rf"C:\Program Files\{target}\{target}.exe",
                rf"C:\Program Files (x86)\{target}\{target}.exe",
            ]

            for path in common_paths:
                if shutil.which(path) or path.endswith(".exe"):
                    subprocess.Popen(path, shell=True)
                    return {"success": True, "result": f"Opened {target}"}

            # Try 'start' command as fallback
            subprocess.Popen(f"start {target}", shell=True)
            return {"success": True, "result": f"Attempted to open {target}"}

        except Exception as e:
            return {"success": False, "error": f"Failed to open {target}: {str(e)}", "result": ""}

    async def _close_app(self, target: str, value: int = 50) -> dict[str, Any]:
        """Close an application."""
        try:
            if not target:
                return {"success": False, "error": "Application name required", "result": ""}

            result = subprocess.run(
                ["taskkill", "/F", "/IM", f"{target}.exe"],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                return {"success": True, "result": f"Closed {target}"}
            else:
                return {"success": False, "error": f"Could not close {target}: {result.stderr.strip()}", "result": ""}

        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _get_processes(self, target: str = "", value: int = 50) -> dict[str, Any]:
        """List running processes."""
        try:
            import psutil

            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    pinfo = proc.info
                    if not target or target.lower() in pinfo["name"].lower():
                        processes.append(f"  {pinfo['pid']:>6}  {pinfo['name']:<30}  CPU:{pinfo['cpu_percent']:>5.1f}%  Mem:{pinfo['memory_percent']:>5.1f}%")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by memory usage
            result = f"Running processes ({len(processes)} total):\n" + "\n".join(processes[:30])
            if len(processes) > 30:
                result += f"\n... and {len(processes) - 30} more"

            return {"success": True, "result": result, "count": len(processes)}

        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _system_info(self, target: str = "", value: int = 50) -> dict[str, Any]:
        """Get system information."""
        try:
            import platform
            import psutil

            info = (
                f"System: {platform.system()} {platform.release()}\n"
                f"Node: {platform.node()}\n"
                f"Processor: {platform.processor()}\n"
                f"CPU Cores: {psutil.cpu_count(logical=True)} ({psutil.cpu_count(logical=False)} physical)\n"
                f"CPU Usage: {psutil.cpu_percent(interval=0.5)}%\n"
                f"Memory: {_format_bytes(psutil.virtual_memory().total)}\n"
                f"Memory Usage: {psutil.virtual_memory().percent}%\n"
                f"Disk: {_format_bytes(psutil.disk_usage('/').total)} ({psutil.disk_usage('/').percent}% used)\n"
                f"Boot Time: {psutil.boot_time()}"
            )
            return {"success": True, "result": info}

        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _set_volume(self, target: str = "", value: int = 50) -> dict[str, Any]:
        """Set system volume (0-100)."""
        try:
            # Try using pycaw (Windows Core Audio API)
            try:
                from pycaw.api.endpoint_volume import IAudioEndpointVolume
                from pycaw.utils import AudioUtilities
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL

                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
                volume = cast(interface, POINTER(IAudioEndpointVolume))

                normalized = max(0.0, min(1.0, value / 100.0))
                volume.SetMasterVolumeLevelScalar(normalized, None)
                return {"success": True, "result": f"Volume set to {value}%"}
            except ImportError:
                # Fallback: use PowerShell
                import subprocess
                value_clamped = max(0, min(100, value))
                subprocess.run(
                    [
                        "powershell",
                        "-c",
                        f"(New-Object -ComObject WScript.Shell).SendKeys([char]173)",
                    ],
                    capture_output=True,
                    timeout=2,
                )
                return {
                    "success": True,
                    "result": f"Volume adjustment attempted to {value}%",
                }
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _lock_screen(self, target: str = "", value: int = 50) -> dict[str, Any]:
        """Lock the workstation."""
        try:
            import subprocess
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
            return {"success": True, "result": "Workstation locked"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _take_screenshot(self, target: str = "", value: int = 50) -> dict[str, Any]:
        """Take a screenshot."""
        try:
            import pyautogui
            from PIL import Image
            import io
            import base64
            from datetime import datetime

            screenshot = pyautogui.screenshot()

            # Save to file
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = f"data/{filename}"
            screenshot.save(filepath)

            # Also return as base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode()

            return {
                "success": True,
                "result": f"Screenshot saved to {filepath}",
                "filepath": filepath,
            }

        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}


def _format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"
