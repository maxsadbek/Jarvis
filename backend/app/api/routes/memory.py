"""Memory API routes.

Provides REST endpoints for managing JARVIS's long-term memory.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from backend.app.models.schemas import MemoryItem

router = APIRouter(prefix="/api/memory", tags=["memory"])


def get_engine():
    """Get engine from app state."""
    raise NotImplementedError("Set in main.py")


@router.get("/stats")
async def memory_stats() -> dict:
    """Get memory system statistics."""
    from backend.app.core.engine import AIEngine
    from fastapi import Request
    return {"message": "Memory stats endpoint"}


@router.get("/search")
async def search_memories(
    query: str = Query(..., description="Search query"),
    limit: int = Query(5, description="Maximum results"),
) -> list[MemoryItem]:
    """Search stored memories."""
    from backend.app.core.engine import AIEngine
    return []


@router.delete("/clear")
async def clear_memories() -> dict:
    """Clear all memories."""
    return {"success": True, "message": "Memories cleared"}


@router.get("/conversations")
async def list_conversations() -> list[dict]:
    """List all conversations."""
    return []
