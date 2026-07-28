"""Chat API routes.

Provides REST endpoints for text-based chat with JARVIS.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger

from backend.app.core.engine import AIEngine
from backend.app.models.schemas import ChatRequest, ChatResponse, Message

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_engine() -> AIEngine:
    """Get the AI engine instance (injected via app state)."""
    from fastapi import Request
    # This will be set in main.py
    raise NotImplementedError("Engine injected via app state")


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a chat message and get AI response."""
    engine = get_engine()
    if not engine.is_llm_ready:
        raise HTTPException(status_code=503, detail="AI engine not ready")

    import time
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
    # Streaming is handled via WebSocket for efficiency
    return {
        "message": "Use WebSocket connection for streaming responses",
        "websocket_path": "/ws",
    }


@router.get("/history/{conversation_id}")
async def get_history(conversation_id: str, limit: int = 50) -> list[Message]:
    """Get conversation history."""
    engine = get_engine()
    if engine._memory:
        messages = await engine._memory.get_conversation_history(
            conversation_id=conversation_id,
            limit=limit,
        )
        return messages
    return []
