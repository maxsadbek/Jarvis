"""Audit Logging System.

Records every tool execution with full context:
- Who called it (session)
- What was called (tool, action, arguments)
- Risk level and permission decision
- Result or error
- Duration
- Whether user confirmed

Provides query and reporting capabilities.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import AuditEntry, PermissionDecision, RiskLevel


class AuditLogger:
    """Tracks all tool executions with full context for security auditing."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._max_memory_entries = 1000
        self._audit_file: Optional[Path] = None

    async def initialize(self) -> bool:
        """Initialize the audit logger."""
        self._audit_file = settings.get_data_path("memory") / "audit_log.jsonl"
        logger.info("Audit logger initialized")
        return True

    async def log(
        self,
        tool_name: str,
        action: str,
        arguments: dict[str, Any],
        status: str = "pending",
        risk_level: RiskLevel = RiskLevel.SAFE,
        permission_decision: PermissionDecision = PermissionDecision.ALLOWED,
        result: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
        user_confirmed: bool = False,
        session_id: Optional[str] = None,
    ) -> AuditEntry:
        """Log a tool execution event.

        Args:
            tool_name: Name of the tool executed.
            action: The specific action.
            arguments: Arguments passed to the tool.
            status: Execution status.
            risk_level: Risk classification.
            permission_decision: Whether it was allowed/denied.
            result: Execution result text.
            error: Error message if failed.
            duration_ms: Execution duration.
            user_confirmed: Whether user confirmed.
            session_id: Session identifier.

        Returns:
            The created AuditEntry.
        """
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            action=action,
            arguments=arguments,
            status=status,
            risk_level=risk_level,
            permission_decision=permission_decision,
            result=result[:500] if result else None,
            error=error[:500] if error else None,
            duration_ms=duration_ms,
            user_confirmed=user_confirmed,
            session_id=session_id,
        )

        self._entries.append(entry)

        # Trim in-memory buffer
        if len(self._entries) > self._max_memory_entries:
            self._entries = self._entries[-self._max_memory_entries:]

        # Append to persistent log file
        await self._append_to_file(entry)

        return entry

    async def query(
        self,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit log entries.

        Args:
            tool_name: Filter by tool name.
            status: Filter by status.
            risk_level: Filter by risk level.
            limit: Maximum results.
            offset: Result offset.

        Returns:
            List of matching AuditEntry objects.
        """
        results = self._entries

        if tool_name:
            results = [e for e in results if e.tool_name == tool_name]
        if status:
            results = [e for e in results if e.status == status]
        if risk_level:
            results = [e for e in results if e.risk_level == risk_level]

        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda e: e.timestamp, reverse=True)

        return results[offset:offset + limit]

    async def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        stats: dict[str, Any] = {
            "total_entries": len(self._entries),
            "by_status": defaultdict(int),
            "by_tool": defaultdict(int),
            "by_risk": defaultdict(int),
            "recent_errors": [],
        }

        for entry in self._entries:
            stats["by_status"][entry.status] += 1
            stats["by_tool"][entry.tool_name] += 1
            stats["by_risk"][entry.risk_level.value] += 1

        # Recent errors
        errors = [e for e in self._entries if e.status == "error"]
        for err in errors[-10:]:
            stats["recent_errors"].append({
                "tool": err.tool_name,
                "action": err.action,
                "error": err.error,
                "time": err.timestamp.isoformat(),
            })

        return stats

    async def get_recent(self, limit: int = 20) -> list[AuditEntry]:
        """Get the most recent audit entries."""
        sorted_entries = sorted(
            self._entries, key=lambda e: e.timestamp, reverse=True
        )
        return sorted_entries[:limit]

    async def _append_to_file(self, entry: AuditEntry) -> None:
        """Append an entry to the JSONL audit file."""
        if not self._audit_file:
            return
        try:
            with open(self._audit_file, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception as e:
            logger.warning(f"Failed to write audit entry: {e}")

    async def clear(self) -> None:
        """Clear the audit log (in-memory only, file kept)."""
        self._entries.clear()
        logger.info("Audit log cleared (in-memory)")
