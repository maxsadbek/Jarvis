"""Memory API routes.

Provides REST endpoints for managing JARVIS's advanced memory system.
Supports: preferences, facts, habits, search, and conversation history.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from backend.app.core.engine import AIEngine
from backend.app.models.schemas import (
    ImportantFact,
    MemoryItem,
    UserHabit,
    UserPreference,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


# Replaceable via app.dependency_overrides in main.py
async def get_engine() -> AIEngine:
    """Get the AI engine instance (overridden via app.dependency_overrides)."""
    raise NotImplementedError("Override via dependency_overrides in main.py")


# --- Utility ---

def _require_memory(engine: AIEngine):
    """Validate that memory is available, raise 503 if not."""
    if not engine or not engine.memory:
        raise HTTPException(status_code=503, detail="Memory not available")
    return engine.memory


# --- Stats ---

@router.get("/stats")
async def memory_stats(
    engine: AIEngine = Depends(get_engine),
) -> dict:
    """Get comprehensive memory system statistics."""
    memory = _require_memory(engine)
    return await memory.get_stats()


# --- Search ---

@router.post("/search", response_model=list[MemoryItem])
async def search_memories(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum results"),
    threshold: float = Query(0.5, description="Relevance threshold"),
    engine: AIEngine = Depends(get_engine),
) -> list[MemoryItem]:
    """Search all memory systems."""
    memory = _require_memory(engine)
    return await memory.search(query=query, limit=limit, threshold=threshold)


# --- Clear ---

@router.delete("/clear")
async def clear_memories(
    confirm: bool = Query(False),
    engine: AIEngine = Depends(get_engine),
) -> dict:
    """Clear all memories.

    Args:
        confirm: Must be True to confirm deletion.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set ?confirm=true to clear all memories.",
        )

    memory = _require_memory(engine)
    await memory.clear()
    return {"success": True, "message": "All memories cleared"}


@router.delete("/clear/conversations")
async def clear_conversation_history(
    engine: AIEngine = Depends(get_engine),
) -> dict:
    """Clear only conversation history, keep preferences and facts."""
    memory = _require_memory(engine)
    await memory.clear_conversations()
    return {"success": True, "message": "Conversation history cleared"}


# --- Preferences ---

@router.get("/preferences", response_model=dict[str, UserPreference])
async def get_preferences(
    category: Optional[str] = Query(None, description="Filter by category"),
    engine: AIEngine = Depends(get_engine),
) -> dict[str, UserPreference]:
    """Get all user preferences."""
    memory = _require_memory(engine)
    prefs = await memory.get_all_preferences()
    if category:
        return {k: v for k, v in prefs.items() if v.category == category}
    return prefs


@router.put("/preferences")
async def update_preferences(
    preferences: dict[str, Any],
    engine: AIEngine = Depends(get_engine),
) -> list[UserPreference]:
    """Update multiple preferences at once.

    Body: {"key": "value", ...}
    """
    memory = _require_memory(engine)
    return await memory.set_preferences(preferences)


@router.get("/preferences/{key}", response_model=UserPreference)
async def get_preference(
    key: str,
    engine: AIEngine = Depends(get_engine),
) -> UserPreference:
    """Get a specific preference by key."""
    memory = _require_memory(engine)
    prefs = await memory.get_all_preferences()
    if key not in prefs:
        raise HTTPException(status_code=404, detail=f"Preference '{key}' not found")
    return prefs[key]


# --- Facts ---

@router.get("/facts", response_model=list[ImportantFact])
async def get_facts(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, description="Maximum results"),
    engine: AIEngine = Depends(get_engine),
) -> list[ImportantFact]:
    """Get stored important facts."""
    memory = _require_memory(engine)
    return await memory.get_facts(category=category, limit=limit)


@router.post("/facts")
async def add_fact(
    fact_text: str = Query(..., description="The fact to remember"),
    category: str = Query("general", description="Fact category"),
    importance: float = Query(0.5, ge=0.0, le=1.0, description="Importance (0-1)"),
    engine: AIEngine = Depends(get_engine),
) -> ImportantFact:
    """Manually add an important fact for JARVIS to remember."""
    memory = _require_memory(engine)
    fact = await memory.add_fact(
        fact_text=fact_text,
        category=category,
        importance=importance,
    )
    if not fact:
        raise HTTPException(status_code=500, detail="Failed to store fact")
    return fact


@router.post("/facts/{fact_id}/verify")
async def verify_fact(
    fact_id: str,
    engine: AIEngine = Depends(get_engine),
) -> dict:
    """Verify a fact as correct (confirmed by user)."""
    memory = _require_memory(engine)
    success = await memory.verify_fact(fact_id)
    return {"success": success, "fact_id": fact_id}


# --- Habits ---

@router.get("/habits", response_model=list[UserHabit])
async def get_habits(
    category: Optional[str] = Query(None, description="Filter by category"),
    min_confidence: float = Query(0.3, description="Minimum confidence (0-1)"),
    engine: AIEngine = Depends(get_engine),
) -> list[UserHabit]:
    """Get learned user habits and patterns."""
    memory = _require_memory(engine)
    return await memory.get_habits(
        category=category,
        min_confidence=min_confidence,
    )
