"""Computer Control Modules.

Specialized tools for controlling the Windows desktop:
- app_control: Open/close apps, switch windows
- system_control: Shutdown, restart, sleep, volume, brightness
- file_control: Create, search, move, organize files
- media_control: Play, pause, next/previous track
"""
from .app_control import AppControlTool
from .system_control import SystemControlTool
from .file_control import FileControlTool
from .media_control import MediaControlTool

__all__ = [
    "AppControlTool",
    "SystemControlTool",
    "FileControlTool",
    "MediaControlTool",
]
