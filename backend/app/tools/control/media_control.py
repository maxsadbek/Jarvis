"""Media Control Module.

Controls media playback on Windows: play, pause, next, previous track.
Uses keyboard media keys and Windows system APIs.
"""

from __future__ import annotations

import subprocess
from typing import Any

from loguru import logger

from backend.app.tools.base import BaseTool
from backend.app.models.schemas import RiskLevel


class MediaControlTool(BaseTool):
    """Control media playback: play, pause, next/previous track, volume."""

    def __init__(self) -> None:
        super().__init__()
        self._risk_level = RiskLevel.SAFE
        self._parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "play",
                        "pause",
                        "toggle_play",
                        "next",
                        "previous",
                        "volume_up",
                        "volume_down",
                        "mute",
                    ],
                    "description": "Media action to perform",
                },
                "app": {
                    "type": "string",
                    "description": "Optional app name to target (spotify, chrome, etc.)",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        return "media_control"

    @property
    def description(self) -> str:
        return "Control media playback: play, pause, next/previous track, volume, mute on Windows"

    async def execute(self, action: str, app: str = "", **kwargs: Any) -> dict[str, Any]:
        handlers = {
            "play": self._play,
            "pause": self._pause,
            "toggle_play": self._toggle_play,
            "next": self._next_track,
            "previous": self._prev_track,
            "volume_up": self._volume_up,
            "volume_down": self._volume_down,
            "mute": self._mute,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown media action: {action}", "result": ""}

        return await handler(app)

    async def _send_media_key(self, key_code: int) -> bool:
        """Send a virtual media key using PowerShell.

        Key codes:
        0xB0 = Next Track
        0xB1 = Previous Track
        0xB2 = Stop
        0xB3 = Play/Pause
        """
        try:
            script = f"""
            $shell = New-Object -ComObject WScript.Shell
            $shell.SendKeys([char]{key_code})
            """
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
                capture_output=True, timeout=5,
            )
            return True
        except Exception as e:
            logger.warning(f"Media key failed: {e}")
            return False

    async def _activate_app(self, app: str) -> None:
        """Try to bring a media app to foreground before sending keys."""
        if not app:
            return
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Name {app} -ErrorAction SilentlyContinue) | Select-Object -First 1 | ForEach-Object {{ $_.MainWindowHandle | ForEach-Object {{ $shell = New-Object -ComObject WScript.Shell; $shell.AppActivate($_.MainWindowTitle) }} }}"],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass

    async def _play(self, app: str = "") -> dict[str, Any]:
        """Start or resume playback."""
        await self._activate_app(app or "spotify")
        await self._send_media_key(0xB3)  # Play/Pause toggle
        return {"success": True, "result": "Playback started"}

    async def _pause(self, app: str = "") -> dict[str, Any]:
        """Pause playback."""
        await self._activate_app(app or "spotify")
        await self._send_media_key(0xB3)  # Play/Pause toggle
        return {"success": True, "result": "Playback paused"}

    async def _toggle_play(self, app: str = "") -> dict[str, Any]:
        """Toggle play/pause."""
        await self._activate_app(app or "spotify")
        await self._send_media_key(0xB3)
        return {"success": True, "result": "Playback toggled"}

    async def _next_track(self, app: str = "") -> dict[str, Any]:
        """Skip to next track."""
        await self._activate_app(app or "spotify")
        await self._send_media_key(0xB0)  # Next Track
        return {"success": True, "result": "Next track"}

    async def _prev_track(self, app: str = "") -> dict[str, Any]:
        """Go to previous track."""
        await self._activate_app(app or "spotify")
        await self._send_media_key(0xB1)  # Previous Track
        return {"success": True, "result": "Previous track"}

    async def _volume_up(self, app: str = "") -> dict[str, Any]:
        """Increase system volume by ~2%."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                 "$shell = New-Object -ComObject WScript.Shell; for($i=0; $i -lt 3; $i++) { $shell.SendKeys([char]175) }"],
                capture_output=True, timeout=5,
            )
            return {"success": True, "result": "Volume increased"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _volume_down(self, app: str = "") -> dict[str, Any]:
        """Decrease system volume by ~2%."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                 "$shell = New-Object -ComObject WScript.Shell; for($i=0; $i -lt 3; $i++) { $shell.SendKeys([char]174) }"],
                capture_output=True, timeout=5,
            )
            return {"success": True, "result": "Volume decreased"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _mute(self, app: str = "") -> dict[str, Any]:
        """Toggle mute."""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                 "$shell = New-Object -ComObject WScript.Shell; $shell.SendKeys([char]173)"],
                capture_output=True, timeout=5,
            )
            return {"success": True, "result": "Volume toggled mute"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}
