"""Chat API routes.

Provides REST endpoints for text-based chat with JARVIS.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from backend.app.core.engine import AIEngine
from backend.app.models.schemas import ChatRequest, ChatResponse, Message

router = APIRouter(prefix="/api/chat", tags=["chat"])


# Replaceable via app.dependency_overrides in main.py
async def get_engine() -> AIEngine:
    """Get the AI engine instance (overridden via app.dependency_overrides)."""
    raise NotImplementedError("Override via dependency_overrides in main.py")


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    engine: AIEngine = Depends(get_engine),
) -> ChatResponse:
    """Send a chat message and get AI response."""
    if not engine.is_llm_ready:
        raise HTTPException(status_code=503, detail="AI engine not ready")

    start = time.time()

    response = await engine.chat(
        message=request.message,
        conversation_id=request.conversation_id or "default",
        stream=False,
        model=request.model,
    )

    elapsed = (time.time() - start) * 1000

    return ChatResponse(
        message=response,
        conversation_id=request.conversation_id or "default",
        tokens_used=response.metadata.get("tokens", {}).get("total_tokens", 0),
        processing_time_ms=elapsed,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> dict:
    """Initiate a streaming chat response (managed via WebSocket)."""
    return {
        "message": "Use WebSocket connection for streaming responses",
        "websocket_path": "/ws",
    }


@router.get("/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    limit: int = 50,
    engine: AIEngine = Depends(get_engine),
) -> list[Message]:
    """Get conversation history."""
    memory = getattr(engine, "_memory", None)
    if memory:
        messages = await memory.get_conversation_history(
            conversation_id=conversation_id,
            limit=limit,
        )
        return messages
    return []
