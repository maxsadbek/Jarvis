"""Plugin Base — Foundation for all JARVIS plugins.

Every plugin extends BasePlugin and can:
- Register new command intents
- Add tool functions
- Handle custom events
- Add startup/shutdown hooks
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class PluginInfo:
    """Metadata about a plugin."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)
    requires_confirmation: bool = False  # Whether plugin actions need user OK


class BasePlugin(ABC):
    """Abstract base class for all JARVIS plugins."""

    def __init__(self) -> None:
        self._registry: Optional["PluginRegistry"] = None
        self._initialized = False

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Plugin metadata."""
        ...

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the plugin. Return True on success."""
        ...

    async def shutdown(self) -> None:
        """Clean up plugin resources."""
        pass

    async def handle_intent(self, intent: str, params: dict[str, Any]) -> Optional[str]:
        """Handle a command intent. Return response text or None.

        Args:
            intent: The intent name (e.g., "get_weather").
            params: Intent parameters.

        Returns:
            Response text to speak/display, or None if not handled.
        """
        return None

    def register_intents(self) -> list[dict[str, Any]]:
        """Register custom intents this plugin handles.

        Returns:
            List of intent definitions: [{"name": "...", "patterns": [...], "action": "..."}]
        """
        return []

    def set_registry(self, registry: "PluginRegistry") -> None:
        """Set the plugin registry reference."""
        self._registry = registry


class PluginRegistry:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self, plugin_dir: str | Path | None = None) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._plugin_dir = Path(plugin_dir) if plugin_dir else Path(__file__).parent

    @property
    def plugins(self) -> dict[str, BasePlugin]:
        return dict(self._plugins)

    async def discover_and_load(self) -> int:
        """Discover and load all plugins from the plugins directory.

        Returns:
            Number of plugins successfully loaded.
        """
        loaded = 0

        # Load built-in plugins
        builtins = self._discover_builtins()
        for name, plugin_cls in builtins:
            try:
                plugin = plugin_cls()
                plugin.set_registry(self)
                ok = await plugin.initialize()
                if ok:
                    self._plugins[name] = plugin
                    loaded += 1
                    logger.info(f"  ✓ Plugin loaded: {plugin.info.name} v{plugin.info.version}")
                else:
                    logger.warning(f"  ✗ Plugin init failed: {name}")
            except Exception as e:
                logger.error(f"  ✗ Plugin load error {name}: {e}")

        # Load external plugins from plugins/ directory
        externals = self._discover_external()
        for name, plugin_cls in externals:
            if name not in self._plugins:
                try:
                    plugin = plugin_cls()
                    plugin.set_registry(self)
                    ok = await plugin.initialize()
                    if ok:
                        self._plugins[name] = plugin
                        loaded += 1
                        logger.info(f"  ✓ Plugin loaded: {plugin.info.name}")
                except Exception as e:
                    logger.error(f"  ✗ External plugin error {name}: {e}")

        return loaded

    def _discover_builtins(self) -> list[tuple[str, type[BasePlugin]]]:
        """Discover plugins from backend/app/plugins/ submodules."""
        builtins: list[tuple[str, type[BasePlugin]]] = []
        try:
            from . import example_plugin
            if hasattr(example_plugin, "ExamplePlugin"):
                builtins.append(("example", example_plugin.ExamplePlugin))
        except Exception:
            pass
        return builtins

    def _discover_external(self) -> list[tuple[str, type[BasePlugin]]]:
        """Discover external plugins from the plugins/ directory."""
        externals: list[tuple[str, type[BasePlugin]]] = []

        if not self._plugin_dir.exists():
            return externals

        for item in self._plugin_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                try:
                    module_name = f"plugins.{item.name}"
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and issubclass(obj, BasePlugin)
                                and obj != BasePlugin):
                            externals.append((item.name, obj))
                except Exception as e:
                    logger.warning(f"Failed to load plugin {item.name}: {e}")

        return externals

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a loaded plugin by name."""
        return self._plugins.get(name)

    async def shutdown_all(self) -> None:
        """Shut down all plugins gracefully."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.warning(f"Plugin shutdown error {name}: {e}")
        self._plugins.clear()

    def get_all_intents(self) -> list[dict[str, Any]]:
        """Collect all intents from all plugins."""
        intents = []
        for plugin in self._plugins.values():
            intents.extend(plugin.register_intents())
        return intents
