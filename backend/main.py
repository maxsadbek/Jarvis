"""JARVIS AI Assistant - Main Application Entry Point.

FastAPI application with WebSocket support for real-time voice/chat.
Run with: uvicorn main:app --reload
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, Query, Request, HTTPException
from loguru import logger

from backend.app.api.middleware import setup_middleware
from backend.app.api.websocket import ConnectionManager
from backend.app.config import settings
from backend.app.core.engine import AIEngine
from backend.app.services import MessageHandler
from backend.app.api.routes import chat as chat_routes, voice as voice_routes, memory as memory_routes
from backend.app.assistant_core import VoicePipeline, PipelineConfig, VoiceAssistantConfig


# --- Global Service Locator ---
# Cleaner than monkey-patching; use app.state for request-scoped access.

_engine: AIEngine | None = None
_connection_manager: ConnectionManager | None = None
_voice_pipeline: VoicePipeline | None = None


async def get_engine(request: Request) -> AIEngine:
    """FastAPI dependency: get the AI engine from app state."""
    eng: AIEngine | None = request.app.state.engine
    if eng is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return eng


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    global _engine, _connection_manager, _voice_pipeline

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")

    # 1. Initialize AI Engine
    _engine = AIEngine()
    await _engine.initialize()

    # 2. Initialize Voice Pipeline
    if settings.is_voice_enabled:
        voice_config = VoiceAssistantConfig.create_default()
        pipeline_config = PipelineConfig(voice=voice_config)
        _voice_pipeline = VoicePipeline(ai_engine=_engine, config=pipeline_config)
        await _voice_pipeline.initialize()
        logger.info("Voice pipeline ready")
    else:
        logger.info("Voice pipeline disabled")

    # 3. Initialize WebSocket manager
    _connection_manager = ConnectionManager()

    # Store in app state for route injection
    app.state.engine = _engine
    app.state.connection_manager = _connection_manager
    app.state.voice_pipeline = _voice_pipeline

    logger.info(f"{settings.APP_NAME} is ready! 🚀")
    yield

    # Shutdown
    logger.info("Shutting down...")
    if _voice_pipeline:
        await _voice_pipeline.shutdown()
    if _engine:
        await _engine.shutdown()
    logger.info("Goodbye! 👋")


# --- Create FastAPI app ---

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
)

setup_middleware(app)


# --- Register REST API Routes ---

# Use FastAPI dependency injection properly via app.state
app.dependency_overrides[chat_routes.get_engine] = get_engine
app.dependency_overrides[voice_routes.get_engine] = get_engine
app.dependency_overrides[memory_routes.get_engine] = get_engine

app.include_router(chat_routes.router)
app.include_router(voice_routes.router)
app.include_router(memory_routes.router)


# --- Voice Pipeline REST endpoints ---

@app.get("/api/voice/pipeline/status")
async def voice_pipeline_status() -> dict:
    """Get voice pipeline status."""
    if not _voice_pipeline:
        return {"status": "disabled", "message": "Voice pipeline not initialized"}
    return {
        "status": "ready" if _voice_pipeline.is_ready else "initializing",
        "listening": _voice_pipeline.is_listening,
        "session": _voice_pipeline.active_session.to_dict() if _voice_pipeline.active_session else None,
        "session_stats": _voice_pipeline.session_manager.get_stats(),
    }


@app.post("/api/voice/pipeline/session/start")
async def start_voice_session(conversation_id: str | None = None) -> dict:
    """Start a new voice interaction session."""
    if not _voice_pipeline:
        raise HTTPException(status_code=503, detail="Voice pipeline not available")
    session = await _voice_pipeline.start_session(conversation_id=conversation_id)
    return {"success": True, "session": session.to_dict()}


@app.post("/api/voice/pipeline/session/end")
async def end_voice_session() -> dict:
    """End the current voice session."""
    if _voice_pipeline:
        await _voice_pipeline.end_session()
    return {"success": True}


# --- Root & Status Endpoints ---

@app.get("/")
async def root() -> dict:
    """Root endpoint with API info."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "chat": "/api/chat",
            "voice": "/api/voice",
            "memory": "/api/memory",
            "websocket": "/ws",
            "status": "/api/status",
        },
    }


@app.get("/api/status")
async def system_status() -> dict:
    """Get complete system status."""
    if not _engine:
        return {"status": "initializing", "message": "Engine is starting up..."}
    status = await _engine.get_status()
    result = status.model_dump()
    result["voice_pipeline_ready"] = _voice_pipeline.is_ready if _voice_pipeline else False
    return result


@app.get("/api/health")
async def health_check() -> dict:
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "llm_ready": _engine.is_llm_ready if _engine else False,
        "connections": _connection_manager.active_count if _connection_manager else 0,
        "voice_ready": _voice_pipeline.is_ready if _voice_pipeline else False,
    }


@app.get("/api/stats")
async def system_stats() -> dict:
    """Get system statistics."""
    stats: dict = {"active_connections": _connection_manager.active_count if _connection_manager else 0}
    if _engine:
        mem_stats = await _engine.get_memory_stats()
        stats["memory"] = mem_stats
        stats["uptime_seconds"] = _engine._start_time
    if _voice_pipeline:
        stats["voice"] = _voice_pipeline.session_manager.get_stats()
    return stats


# --- WebSocket Handler ---

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(default=""),
):
    """WebSocket endpoint for real-time communication.

    Delegates message handling to the MessageHandler service
    for clean separation of concerns.
    """
    if not client_id:
        client_id = str(uuid.uuid4())

    if not _connection_manager:
        await websocket.close(code=1011, reason="Server not ready")
        return

    handler = MessageHandler(
        engine=_engine,
        connection_manager=_connection_manager,
        voice_pipeline=_voice_pipeline,
    )

    # Handle the connection lifecycle, routing all messages through MessageHandler
    async def on_message(client_id: str, msg_type: str, data: str | bytes) -> None:
        await handler.handle(client_id, msg_type, data)

    await _connection_manager.handle_client(websocket, client_id, on_message)


# --- Run ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
