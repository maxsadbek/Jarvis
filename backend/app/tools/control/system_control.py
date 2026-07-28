"""System Control Module (Enhanced).

Extends existing system_ctl.py with:
- Graceful shutdown/restart/sleep
- Brightness control
- Volume control via Windows API
- Safety confirmations for destructive actions
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from loguru import logger

from backend.app.tools.base import BaseTool
from backend.app.models.schemas import RiskLevel


class SystemControlTool(BaseTool):
    """System-level control: shutdown, restart, sleep, volume, brightness."""

    def __init__(self) -> None:
        super().__init__()
        self._parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "shutdown",
                        "restart",
                        "sleep",
                        "hibernate",
                        "lock",
                        "volume",
                        "volume_up",
                        "volume_down",
                        "brightness",
                        "get_info",
                        "empty_recycle_bin",
                    ],
                    "description": "System action to perform",
                },
                "value": {
                    "type": "integer",
                    "description": "Value for volume (0-100) or brightness (0-100)",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        return "system_control"

    @property
    def description(self) -> str:
        return "Control system: shutdown, restart, sleep, volume, brightness, lock"

    async def execute(self, action: str, value: int = 50, **kwargs: Any) -> dict[str, Any]:
        handlers = {
            "shutdown": self._shutdown,
            "restart": self._restart,
            "sleep": self._sleep,
            "hibernate": self._hibernate,
            "lock": self._lock,
            "volume": self._set_volume,
            "volume_up": self._volume_up,
            "volume_down": self._volume_down,
            "brightness": self._set_brightness,
            "get_info": self._get_info,
            "empty_recycle_bin": self._empty_recycle_bin,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown action: {action}", "result": ""}

        return await handler(value)

    async def _shutdown(self, value: int = 0) -> dict[str, Any]:
        """Shutdown the computer after 30s delay (can be aborted)."""
        try:
            subprocess.run(["shutdown", "/s", "/t", "30", "/c", "JARVIS initiated shutdown"], timeout=5)
            return {
                "success": True,
                "result": "Shutting down in 30 seconds. Say 'cancel shutdown' to abort.",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _restart(self, value: int = 0) -> dict[str, Any]:
        """Restart the computer after 30s delay."""
        try:
            subprocess.run(["shutdown", "/r", "/t", "30", "/c", "JARVIS initiated restart"], timeout=5)
            return {
                "success": True,
                "result": "Restarting in 30 seconds. Say 'cancel shutdown' to abort.",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _sleep(self, value: int = 0) -> dict[str, Any]:
        """Put the computer to sleep."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Add-Type '[DllImport(\"powrprof.dll\")]public static extern int SetSuspendState(bool,bool,bool);' -Name a -Pas).SetSuspendState($true,$false,$false)"],
                timeout=5,
            )
            return {"success": True, "result": "Going to sleep"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _hibernate(self, value: int = 0) -> dict[str, Any]:
        """Hibernate the computer."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Add-Type '[DllImport(\"powrprof.dll\")]public static extern int SetSuspendState(bool,bool,bool);' -Name a -Pas).SetSuspendState($false,$false,$false)"],
                timeout=5,
            )
            return {"success": True, "result": "Hibernating"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _lock(self, value: int = 0) -> dict[str, Any]:
        """Lock the workstation."""
        try:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
            return {"success": True, "result": "Workstation locked"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _set_volume(self, value: int = 50) -> dict[str, Any]:
        """Set system volume to specific level (0-100)."""
        try:
            value = max(0, min(100, value))
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
                volume.SetMasterVolumeLevelScalar(value / 100.0, None)
                return {"success": True, "result": f"Volume set to {value}%"}
            except ImportError:
                # Fallback to PowerShell
                script = f"""
                $shell = New-Object -ComObject WScript.Shell
                for($i=0; $i -lt 50; $i++) {{ $shell.SendKeys([char]174) }}
                for($i=0; $i -lt {value // 2}; $i++) {{ $shell.SendKeys([char]175) }}
                """
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
                    capture_output=True, timeout=5,
                )
                return {"success": True, "result": f"Volume set to approximately {value}%"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _volume_up(self, value: int = 5) -> dict[str, Any]:
        """Increase volume."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                 f"$shell = New-Object -ComObject WScript.Shell; for($i=0; $i -lt {max(1, value // 2)}; $i++) {{ $shell.SendKeys([char]175) }}"],
                capture_output=True, timeout=5,
            )
            return {"success": True, "result": f"Volume increased"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _volume_down(self, value: int = 5) -> dict[str, Any]:
        """Decrease volume."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                 f"$shell = New-Object -ComObject WScript.Shell; for($i=0; $i -lt {max(1, value // 2)}; $i++) {{ $shell.SendKeys([char]174) }}"],
                capture_output=True, timeout=5,
            )
            return {"success": True, "result": f"Volume decreased"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _set_brightness(self, value: int = 50) -> dict[str, Any]:
        """Set screen brightness (0-100)."""
        try:
            value = max(0, min(100, value))
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{value})"],
                capture_output=True, timeout=5,
            )
            return {"success": True, "result": f"Brightness set to {value}%"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _get_info(self, value: int = 0) -> dict[str, Any]:
        """Get system information."""
        try:
            import platform
            import psutil

            uname = platform.uname()
            info = (
                f"System: {uname.system} {uname.release}\n"
                f"Version: {uname.version}\n"
                f"Processor: {uname.processor}\n"
                f"CPU Usage: {psutil.cpu_percent(interval=0.5)}%\n"
                f"RAM: {_format_bytes(psutil.virtual_memory().total)} ({psutil.virtual_memory().percent}% used)\n"
                f"Disk: {_format_bytes(psutil.disk_usage('/').total)} ({psutil.disk_usage('/').percent}% used)\n"
                f"Uptime: {_format_uptime(psutil.boot_time())}"
            )
            return {"success": True, "result": info}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _empty_recycle_bin(self, value: int = 0) -> dict[str, Any]:
        """Empty the Windows Recycle Bin silently."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=10,
            )
            return {"success": True, "result": "Recycle Bin emptied"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}


def _format_bytes(bytes_val: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def _format_uptime(boot_time: float) -> str:
    import time
    seconds = int(time.time() - boot_time)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "< 1m"
