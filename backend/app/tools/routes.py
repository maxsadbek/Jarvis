"""Tool API Routes.

Provides REST endpoints for:
- Executing tools directly
- Managing permission rules
- Viewing audit logs
- Managing automation tasks
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from backend.app.models.schemas import (
    AuditEntry,
    AutomationTask,
    PermissionRule,
    ToolCall,
    ToolName,
)

router = APIRouter(prefix="/api/tools", tags=["tools"])


def get_engine():
    """Get engine from app state (set in main.py)."""
    raise NotImplementedError("Set in main.py")


# --- Tool Execution ---


@router.post("/execute")
async def execute_tool(
    tool_name: str = Query(..., description="Tool name"),
    action: str = Query(..., description="Action to perform"),
    params: dict[str, Any] = {},
    auto_confirm: bool = Query(False, description="Auto-confirm risky actions"),
) -> ToolCall:
    """Execute a tool directly."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    # Create tool call
    tool_call = ToolCall(
        id=str(uuid.uuid4()),
        name=ToolName(tool_name),
        arguments={**params, "action": action},
    )

    result = await engine._tool_registry.execute_tool(
        tool_call=tool_call,
        auto_confirm=auto_confirm,
    )

    return result


@router.post("/confirm")
async def confirm_tool_execution(
    tool_call_id: str = Query(...),
    session_id: str = Query(...),
) -> dict:
    """Confirm a pending tool execution (for high-risk actions)."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    permissions = await engine._tool_registry.get_permissions()
    if not permissions:
        raise HTTPException(status_code=503, detail="Permissions not available")

    await permissions.confirm_action("tool_call", tool_call_id, session_id)
    return {"success": True, "message": "Tool execution confirmed"}


# --- Tool Listing ---


@router.get("/list")
async def list_tools() -> list[dict[str, Any]]:
    """List all available tools with their capabilities."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    tools = []
    for name, tool in engine._tool_registry.tools.items():
        tools.append({
            "name": name,
            "description": tool.description,
            "parameters": tool.parameters,
            "risk_level": tool.risk_level.value,
        })

    return tools


# --- Audit Log ---


@router.get("/audit", response_model=list[AuditEntry])
async def get_audit_log(
    tool_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[AuditEntry]:
    """View the audit log for tool executions."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    audit = await engine._tool_registry.get_audit_log()
    if not audit:
        return []

    return await audit.query(
        tool_name=tool_name,
        status=status,
        limit=limit,
    )


@router.get("/audit/stats")
async def get_audit_stats() -> dict:
    """Get audit log statistics."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    audit = await engine._tool_registry.get_audit_log()
    if not audit:
        return {}

    return await audit.get_stats()


# --- Permissions ---


@router.get("/permissions/rules", response_model=list[PermissionRule])
async def get_permission_rules() -> list[PermissionRule]:
    """Get all permission rules."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    permissions = await engine._tool_registry.get_permissions()
    if not permissions:
        return []

    return await permissions.get_rules()


@router.post("/permissions/rules")
async def add_permission_rule(rule: PermissionRule) -> PermissionRule:
    """Add a permission rule."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    permissions = await engine._tool_registry.get_permissions()
    if not permissions:
        raise HTTPException(status_code=503, detail="Permissions not available")

    await permissions.add_rule(rule)
    return rule


@router.delete("/permissions/rules/{rule_id}")
async def remove_permission_rule(rule_id: str) -> dict:
    """Remove a permission rule."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    permissions = await engine._tool_registry.get_permissions()
    if not permissions:
        raise HTTPException(status_code=503, detail="Permissions not available")

    success = await permissions.remove_rule(rule_id)
    return {"success": success}


# --- Automation Tasks ---


@router.get("/automation/tasks", response_model=list[AutomationTask])
async def get_automation_tasks(
    tag: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
) -> list[AutomationTask]:
    """Get all automation tasks."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    return await engine._automation.get_all_tasks(tag=tag, enabled_only=enabled_only)


@router.post("/automation/tasks")
async def create_automation_task(
    name: str = Query(...),
    description: Optional[str] = Query(None),
    steps: list[dict[str, Any]] = [],
    schedule: Optional[str] = Query(None),
    tags: Optional[list[str]] = Query(None),
) -> AutomationTask:
    """Create a new automation task."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    return await engine._automation.create_task(
        name=name,
        description=description,
        steps=steps,
        schedule=schedule,
        tags=tags,
    )


@router.post("/automation/tasks/{task_id}/execute")
async def execute_automation_task(task_id: str) -> dict:
    """Execute an automation task."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    result = await engine._automation.execute_task(task_id)
    return result


@router.delete("/automation/tasks/{task_id}")
async def delete_automation_task(task_id: str) -> dict:
    """Delete an automation task."""
    engine = get_engine()
    if not engine or not engine._tool_registry:
        raise HTTPException(status_code=503, detail="Tool system not available")

    success = await engine._automation.delete_task(task_id)
    return {"success": success}
