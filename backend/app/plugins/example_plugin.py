"""Example Plugin — Template for creating new JARVIS plugins.

Shows the minimal structure required.
Copy this file to create new plugins.
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from backend.app.plugins.base import BasePlugin, PluginInfo


class ExamplePlugin(BasePlugin):
    """Template plugin showing the JARVIS plugin API."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="Example Plugin",
            version="1.0.0",
            description="Template for JARVIS plugins",
            author="JARVIS Team",
        )

    async def initialize(self) -> bool:
        """Initialize plugin resources."""
        logger.info("Example plugin initialized")
        return True

    async def handle_intent(self, intent: str, params: dict[str, Any]) -> Optional[str]:
        """Handle intents registered by this plugin."""
        if intent == "example_action":
            return f"Performed example action with params: {params}"
        return None

    def register_intents(self) -> list[dict[str, Any]]:
        """Register custom intents."""
        return [
            {
                "name": "example_action",
                "patterns": ["example", "test plugin"],
                "action": "run_example",
            },
        ]
