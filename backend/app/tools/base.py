"""Enhanced Tool System - Base classes and permission-aware registry.

JARVIS can use tools to interact with the computer and web.
Each tool has a risk level and requires permission checks.
All executions are audited.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import (
    AuditEntry,
    PermissionDecision,
    RiskLevel,
    ToolCall,
    ToolName,
)
from backend.app.tools.audit import AuditLogger
from backend.app.tools.permissions import PermissionManager


class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self) -> None:
        self._name: str = ""
        self._description: str = ""
        self._parameters: dict[str, Any] = {}
        self._risk_level: RiskLevel = RiskLevel.SAFE

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

    @property
    def risk_level(self) -> RiskLevel:
        """Default risk level for this tool."""
        return self._risk_level

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
    """Permission-aware registry of all available tools.

    Features:
    - Tool registration and discovery
    - Permission checking before execution
    - Audit logging for all executions
    - Risk-based execution control
    - Integration with AutomationEngine
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._permissions: Optional[PermissionManager] = None
        self._audit: Optional[AuditLogger] = None

    @property
    def tools(self) -> dict[str, BaseTool]:
        return self._tools

    async def initialize(self) -> None:
        """Discover and register all enabled tools with security systems."""
        from .web_search import WebSearchTool
        from .file_ops import FileOpsTool
        from .system_ctl import SystemControlTool
        from .browser_tool import BrowserTool
        from .code_exec import CodeExecutionTool
        from .command_runner import CommandRunnerTool

        tool_classes = {
            "web_search": WebSearchTool,
            "file_ops": FileOpsTool,
            "system_ctl": SystemControlTool,
            "browser": BrowserTool,
            "code_exec": CodeExecutionTool,
            "command_runner": CommandRunnerTool,
        }

        # Initialize security subsystems
        self._permissions = PermissionManager()
        await self._permissions.initialize()

        self._audit = AuditLogger()
        await self._audit.initialize()

        # Register tools
        for tool_name in settings.ENABLED_TOOLS:
            if tool_name in tool_classes:
                try:
                    tool = tool_classes[tool_name]()
                    self._tools[tool.name] = tool
                    logger.info(f"  ✓ Tool loaded: {tool.name}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to load tool {tool_name}: {e}")

        logger.info(f"Tool registry ready: {len(self._tools)} tools, permissions active")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """Get tools formatted for LLM function calling."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    async def execute_tool(
        self,
        tool_call: ToolCall,
        session_id: Optional[str] = None,
        auto_confirm: bool = False,
    ) -> ToolCall:
        """Execute a tool call with permission checking and audit logging.

        Args:
            tool_call: The tool call to execute.
            session_id: Optional session for permission overrides.
            auto_confirm: Auto-confirm dangerous actions (user consented).

        Returns:
            The same tool call with result populated and status updated.
        """
        tool = self.get_tool(
            tool_call.name.value if hasattr(tool_call.name, "value") else tool_call.name
        )

        if not tool:
            tool_call.status = "error"
            tool_call.error = f"Tool '{tool_call.name}' not found"
            return tool_call

        # Determine action from arguments
        action = tool_call.arguments.get("action", tool_call.arguments.get("operation", "execute"))

        # 1. Check permissions
        if self._permissions:
            decision, risk, reason = await self._permissions.check_permission(
                tool_name=tool.name,
                action=action,
                arguments=tool_call.arguments,
                session_id=session_id,
            )

            tool_call.risk_level = risk

            if decision == PermissionDecision.DENIED:
                tool_call.status = "denied"
                tool_call.error = reason or "Permission denied"
                await self._log_audit(tool.name, action, tool_call, "denied")
                return tool_call

            if decision == PermissionDecision.REQUIRES_CONFIRMATION and not auto_confirm:
                tool_call.status = "pending"
                tool_call.requires_confirmation = True
                tool_call.error = reason or "Requires confirmation"
                return tool_call

            if decision == PermissionDecision.REQUIRES_PASSWORD and not auto_confirm:
                tool_call.status = "pending"
                tool_call.requires_confirmation = True
                tool_call.error = "This action requires your password to proceed"
                return tool_call

        # 2. Execute
        start_time = time.time()
        tool_call.status = "running"

        logger.info(f"Executing tool: {tool.name}.{action} (risk: {tool_call.risk_level.value})")

        try:
            result = await tool.execute(**tool_call.arguments)

            duration_ms = (time.time() - start_time) * 1000
            tool_call.status = "completed" if result.get("success") else "error"
            tool_call.result = result.get("result", str(result))[:2000]
            tool_call.error = result.get("error")

            if tool_call.status == "completed":
                logger.info(f"  ✓ {tool.name}.{action} completed ({duration_ms:.0f}ms)")
            else:
                logger.warning(f"  ✗ {tool.name}.{action} failed: {tool_call.error}")

            # 3. Audit log
            await self._log_audit(
                tool.name, action, tool_call,
                "completed" if result.get("success") else "error",
                duration_ms,
                auto_confirm,
                session_id,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            tool_call.status = "error"
            tool_call.error = str(e)
            logger.error(f"  ✗ {tool.name}.{action} exception: {e}")

            await self._log_audit(
                tool.name, action, tool_call, "error", duration_ms, auto_confirm, session_id
            )

        return tool_call

    async def _log_audit(
        self,
        tool_name: str,
        action: str,
        tool_call: ToolCall,
        status: str,
        duration_ms: float = 0.0,
        user_confirmed: bool = False,
        session_id: Optional[str] = None,
    ) -> None:
        """Log tool execution to audit system."""
        if not self._audit:
            return

        await self._audit.log(
            tool_name=tool_name,
            action=action,
            arguments=tool_call.arguments,
            status=status,
            risk_level=tool_call.risk_level,
            permission_decision=(
                PermissionDecision.ALLOWED if status != "denied"
                else PermissionDecision.DENIED
            ),
            result=tool_call.result,
            error=tool_call.error,
            duration_ms=duration_ms,
            user_confirmed=user_confirmed,
            session_id=session_id,
        )

    async def get_audit_log(self) -> AuditLogger:
        """Get the audit logger instance."""
        return self._audit

    async def get_permissions(self) -> PermissionManager:
        """Get the permission manager instance."""
        return self._permissions
