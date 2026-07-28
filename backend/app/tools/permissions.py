"""Permission System for Secure Tool Execution.

Controls which tools and actions JARVIS can perform based on:
- Risk level (safe, low, medium, high, critical)
- User-defined allowed/denied rules
- Confirmation requirements for dangerous actions
- Rate limiting to prevent abuse
- Session-based permission overrides
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import (
    AuditEntry,
    PermissionDecision,
    PermissionRule,
    RiskLevel,
    ToolCall,
)


class RiskClassifier:
    """Classifies tool actions by risk level."""

    # Risk level mappings for known tool/action combinations
    ACTION_RISK: dict[str, dict[str, RiskLevel]] = {
        "web_search": {
            "*": RiskLevel.SAFE,
        },
        "file_ops": {
            "read": RiskLevel.SAFE,
            "info": RiskLevel.SAFE,
            "list": RiskLevel.SAFE,
            "search": RiskLevel.SAFE,
            "write": RiskLevel.LOW,
            "delete": RiskLevel.HIGH,
        },
        "system_ctl": {
            "system_info": RiskLevel.SAFE,
            "get_processes": RiskLevel.SAFE,
            "screenshot": RiskLevel.LOW,
            "open_app": RiskLevel.LOW,
            "volume": RiskLevel.LOW,
            "close_app": RiskLevel.MEDIUM,
            "lock_screen": RiskLevel.MEDIUM,
        },
        "code_exec": {
            "run_python": RiskLevel.MEDIUM,
            "run_shell": RiskLevel.HIGH,
            "run_node": RiskLevel.MEDIUM,
        },
        "browser": {
            "get": RiskLevel.SAFE,
            "search": RiskLevel.SAFE,
            "click": RiskLevel.LOW,
            "fill_form": RiskLevel.LOW,
            "screenshot": RiskLevel.LOW,
        },
        "command_runner": {
            "run": RiskLevel.HIGH,
            "run_approved": RiskLevel.MEDIUM,
        },
    }

    @classmethod
    def get_risk(cls, tool_name: str, action: str) -> RiskLevel:
        """Get the risk level for a tool action.

        Args:
            tool_name: Name of the tool.
            action: The specific action.

        Returns:
            RiskLevel classification.
        """
        tool_actions = cls.ACTION_RISK.get(tool_name, {})
        # Try specific action match first, then wildcard
        risk = tool_actions.get(action) or tool_actions.get("*")
        if risk:
            return risk
        # Default: treat unknown actions as medium risk
        return RiskLevel.MEDIUM

    @classmethod
    def requires_confirmation(cls, risk_level: RiskLevel) -> bool:
        """Check if a risk level requires user confirmation.

        Args:
            risk_level: The risk level to check.

        Returns:
            True if user confirmation is needed.
        """
        return risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @classmethod
    def requires_password(cls, risk_level: RiskLevel) -> bool:
        """Check if a risk level requires password.

        Args:
            risk_level: The risk level to check.

        Returns:
            True if password is needed.
        """
        return risk_level == RiskLevel.CRITICAL


class PermissionManager:
    """Manages permissions for tool execution.

    Features:
    - Risk-based classification
    - User-defined allow/deny rules
    - Auto-confirm for trusted actions
    - Rate limiting per tool
    - Session-based temporary overrides
    """

    def __init__(self) -> None:
        self._rules: dict[str, PermissionRule] = {}
        self._rate_counters: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._session_overrides: dict[str, dict[str, PermissionDecision]] = defaultdict(dict)
        self._initialized = False

    async def initialize(self) -> bool:
        """Load permission rules from persistent storage."""
        try:
            import json
            rules_file = settings.get_data_path("memory") / "permissions.json"
            if rules_file.exists():
                with open(rules_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        rule = PermissionRule(**item)
                        self._rules[rule.id] = rule
            logger.info(f"Permission manager initialized ({len(self._rules)} rules)")
        except Exception as e:
            logger.warning(f"Could not load permission rules: {e}")

        self._initialized = True
        return True

    async def check_permission(
        self,
        tool_name: str,
        action: str,
        arguments: dict[str, Any],
        session_id: Optional[str] = None,
    ) -> tuple[PermissionDecision, RiskLevel, str]:
        """Check if a tool action is permitted.

        Args:
            tool_name: Tool name.
            action: Action name.
            arguments: Action arguments.
            session_id: Optional session for overrides.

        Returns:
            Tuple of (decision, risk_level, reason).
        """
        risk = RiskClassifier.get_risk(tool_name, action)

        # 1. Check session overrides first
        if session_id:
            override = self._session_overrides.get(session_id, {}).get(f"{tool_name}:{action}")
            if override:
                return override, risk, "Session override"

        # 2. Check specific rules
        for rule in self._rules.values():
            if rule.tool_name == tool_name and (rule.action is None or rule.action == action):
                if rule.decision == PermissionDecision.DENIED:
                    return PermissionDecision.DENIED, risk, rule.reason or "Blocked by rule"
                if rule.decision == PermissionDecision.ALLOWED and rule.auto_confirm:
                    # Check rate limit
                    if await self._check_rate_limit(tool_name, action, rule.max_calls_per_minute):
                        return PermissionDecision.ALLOWED, risk, "Auto-confirmed"
                    return PermissionDecision.DENIED, risk, "Rate limit exceeded"

        # 3. Check risk-based default
        if risk == RiskLevel.CRITICAL:
            return PermissionDecision.REQUIRES_PASSWORD, risk, "Critical action requires password"
        if risk == RiskLevel.HIGH:
            return PermissionDecision.REQUIRES_CONFIRMATION, risk, "High-risk action requires confirmation"
        if risk == RiskLevel.MEDIUM:
            return PermissionDecision.REQUIRES_CONFIRMATION, risk, "Medium-risk action recommended confirmation"

        # 4. Safe/Low risk: allowed by default
        return PermissionDecision.ALLOWED, risk, ""

    async def confirm_action(
        self,
        tool_name: str,
        action: str,
        session_id: str,
        duration_minutes: int = 30,
    ) -> None:
        """Temporarily allow an action for a session.

        Args:
            tool_name: Tool to allow.
            action: Action to allow.
            session_id: Session ID.
            duration_minutes: How long to allow (default 30 min).
        """
        self._session_overrides[session_id][f"{tool_name}:{action}"] = PermissionDecision.ALLOWED
        logger.info(f"Action confirmed: {tool_name}.{action} for session {session_id[:8]}...")

    async def add_rule(self, rule: PermissionRule) -> None:
        """Add a permission rule."""
        self._rules[rule.id] = rule
        await self._persist()

    async def remove_rule(self, rule_id: str) -> bool:
        """Remove a permission rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            await self._persist()
            return True
        return False

    async def get_rules(self) -> list[PermissionRule]:
        """Get all permission rules."""
        return list(self._rules.values())

    async def _check_rate_limit(self, tool_name: str, action: str, max_per_minute: int) -> bool:
        """Check if action is within rate limits.

        Args:
            tool_name: Tool name.
            action: Action name.
            max_per_minute: Max calls per minute (0 = unlimited).

        Returns:
            True if allowed, False if rate limited.
        """
        if max_per_minute <= 0:
            return True

        now = time.time()
        key = f"{tool_name}:{action}"
        calls = self._rate_counters[tool_name][key]

        # Remove calls older than 1 minute
        cutoff = now - 60
        calls[:] = [t for t in calls if t > cutoff]
        calls.append(now)

        return len(calls) <= max_per_minute

    async def clear_session_overrides(self, session_id: str) -> None:
        """Clear all temporary overrides for a session."""
        if session_id in self._session_overrides:
            del self._session_overrides[session_id]

    async def _persist(self) -> None:
        """Persist permission rules to disk."""
        try:
            import json
            rules_file = settings.get_data_path("memory") / "permissions.json"
            data = [rule.model_dump() for rule in self._rules.values()]
            with open(rules_file, "w") as f:
                json.dump(data, f, default=str, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist permissions: {e}")
