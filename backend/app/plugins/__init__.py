"""Plugin System — Extensible JARVIS Architecture.

Plugins can add new capabilities without modifying core code.
Each plugin is a Python module in plugins/ that registers:
- New intents/commands
- New tools/actions
- Custom handlers
"""
from .base import BasePlugin, PluginInfo, PluginRegistry

__all__ = [
    "BasePlugin",
    "PluginInfo",
    "PluginRegistry",
]
