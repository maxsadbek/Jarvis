"""Tool System - Base classes and registry.

JARVIS can use tools to interact with the computer and web.
Each tool is a modular plugin that the AI can invoke.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import ToolCall, ToolName


class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self) -> None:
        self._name: str = ""
        self._description: str = ""
        self._parameters: dict[str, Any] = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used for invocation."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        return self._parameters

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            Result dictionary with 'success', 'result', and optionally 'error'.
        """
        ...

    def to_openai_format(self) -> dict[str, Any]:
        """Format tool as OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry of all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    @property
    def tools(self) -> dict[str, BaseTool]:
        return self._tools

    async def initialize(self) -> None:
        """Discover and register all enabled tools."""
        from .web_search import WebSearchTool
        from .file_ops import FileOpsTool
        from .system_ctl import SystemControlTool

        tool_classes = {
            "web_search": WebSearchTool,
            "file_ops": FileOpsTool,
            "system_ctl": SystemControlTool,
        }

        for tool_name in settings.ENABLED_TOOLS:
            if tool_name in tool_classes:
                try:
                    tool = tool_classes[tool_name]()
                    self._tools[tool.name] = tool
                    logger.info(f"  ✓ Tool loaded: {tool.name}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to load tool {tool_name}: {e}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """Get tools formatted for LLM function calling."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    async def execute_tool(self, tool_call: ToolCall) -> ToolCall:
        """Execute a tool call and return the result.

        Args:
            tool_call: The tool call to execute.

        Returns:
            The same tool call with result populated.
        """
        tool = self.get_tool(tool_call.name.value if hasattr(tool_call.name, "value") else tool_call.name)

        if not tool:
            tool_call.status = "error"
            tool_call.error = f"Tool '{tool_call.name}' not found"
            return tool_call

        try:
            tool_call.status = "running"
            logger.info(f"Executing tool: {tool_call.name}")

            result = await tool.execute(**tool_call.arguments)

            tool_call.status = "completed" if result.get("success") else "error"
            tool_call.result = result.get("result", str(result))
            tool_call.error = result.get("error")

            if tool_call.status == "completed":
                logger.info(f"  ✓ Tool {tool_call.name} completed")
            else:
                logger.warning(f"  ✗ Tool {tool_call.name} failed: {tool_call.error}")

        except Exception as e:
            tool_call.status = "error"
            tool_call.error = str(e)
            logger.error(f"  ✗ Tool {tool_call.name} exception: {e}")

        return tool_call
