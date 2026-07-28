"""JARVIS AI Assistant - Main Application Entry Point.

FastAPI application with WebSocket support for real-time voice/chat.
Run with: uvicorn main:app --reload
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, Query, Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from backend.app.api.middleware import setup_middleware
from backend.app.api.websocket import ConnectionManager
from backend.app.config import settings
from backend.app.core.engine import AIEngine
from backend.app.models.schemas import ConnectionState
from backend.app.api.routes import chat as chat_routes, voice as voice_routes, memory as memory_routes


# --- Global instances ---
engine: AIEngine | None = None
connection_manager: ConnectionManager | None = None


# --- Dependency Injection ---

async def get_engine() -> AIEngine:
    """Dependency: get the AI engine instance."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return engine


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    global engine, connection_manager

    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"LLM Provider: {'OpenRouter' if settings.OPENROUTER_API_KEY else 'Not configured'}")
    logger.info(f"Voice: STT={settings.STT_ENGINE}, TTS={settings.TTS_ENGINE}")

    # Initialize engine
    engine = AIEngine()
    await engine.initialize()

    # Initialize connection manager
    connection_manager = ConnectionManager()

    # Store in app state for route injection
    app.state.engine = engine
    app.state.connection_manager = connection_manager

    logger.info(f"{settings.APP_NAME} is ready! 🚀")
    yield

    # Shutdown
    logger.info("Shutting down...")
    if engine:
        await engine.shutdown()
    logger.info("Goodbye! 👋")


# --- Create FastAPI app ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
)

# Setup middleware (CORS, logging, etc.)
setup_middleware(app)


# --- Register REST API Routes ---

# Inject engine into route dependencies
async def get_engine_dep(request: Request) -> AIEngine:
    eng = request.app.state.engine
    if eng is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return eng

# Override the dependency in route modules
chat_routes.get_engine = get_engine_dep
voice_routes.get_engine = get_engine_dep
memory_routes.get_engine = get_engine_dep

app.include_router(chat_routes.router)
app.include_router(voice_routes.router)
app.include_router(memory_routes.router)


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
    if not engine:
        return {"status": "initializing", "message": "Engine is starting up..."}
    status = await engine.get_status()
    return status.model_dump()


@app.get("/api/health")
async def health_check() -> dict:
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "llm_ready": engine.is_llm_ready if engine else False,
        "connections": connection_manager.active_count if connection_manager else 0,
    }


@app.get("/api/stats")
async def system_stats() -> dict:
    """Get system statistics."""
    if engine:
        mem_stats = await engine.get_memory_stats()
        return {
            "uptime_seconds": engine._start_time,
            "memory": mem_stats,
            "active_connections": connection_manager.active_count if connection_manager else 0,
        }
    return {}


# --- WebSocket Handler ---

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(default=""),
):
    """WebSocket endpoint for real-time communication.

    Supports:
    - text: Text chat messages
    - audio: Binary audio chunks for voice
    - command: Client commands (start/stop listening, etc.)
    """
    if not client_id:
        client_id = str(uuid.uuid4())

    if not connection_manager:
        await websocket.close(code=1011, reason="Server not ready")
        return

    # Define the message handler
    async def handle_message(client_id: str, msg_type: str, data: Any):
        """Handle incoming WebSocket messages."""
        if not engine:
            await connection_manager.send_error(client_id, "engine_not_ready", "Engine is initializing")
            return

        if msg_type == "chat":
            # Text chat message
            conversation_id = connection_manager.get_conversation_id(client_id) or "default"
            text = data.get("text", "") if isinstance(data, dict) else str(data)

            if not text.strip():
                return

            # Update state
            await connection_manager.send_state(client_id, ConnectionState.PROCESSING)

            # Get AI response
            response = await engine.chat(
                message=text,
                conversation_id=conversation_id,
                stream=False,
            )

            # Send response
            await connection_manager.send_text(client_id, response.content, {
                "conversation_id": conversation_id,
                "type": response.type.value,
            })

            # If TTS is available, synthesize and send audio
            if settings.TTS_ENGINE and response.content:
                try:
                    from backend.app.voice.tts import TextToSpeech
                    tts = TextToSpeech()
                    if await tts.initialize():
                        await connection_manager.send_state(client_id, ConnectionState.SPEAKING)
                        async for chunk in tts.synthesize_stream(response.content):
                            await connection_manager.send_audio_chunk(client_id, chunk)
                except Exception as e:
                    logger.warning(f"TTS failed: {e}")

            await connection_manager.send_state(client_id, ConnectionState.CONNECTED)

        elif msg_type == "command":
            # Client commands
            action = data.get("action", "") if isinstance(data, dict) else ""
            params = data.get("params", {}) if isinstance(data, dict) else {}

            if action == "set_conversation":
                conv_id = params.get("id", str(uuid.uuid4()))
                connection_manager.set_conversation_id(client_id, conv_id)
                await connection_manager.send_text(client_id, f"Conversation ID: {conv_id}")

            elif action == "clear_memory":
                if engine:
                    await engine.clear_memory()
                await connection_manager.send_text(client_id, "Memory cleared")

            elif action == "search_memory":
                query = params.get("query", "")
                if engine and query:
                    results = await engine.search_memories(query)
                    text = "Memory search results:\n" + "\n".join(
                        [f"- {r.content[:200]}" for r in results]
                    ) if results else "No relevant memories found."
                    await connection_manager.send_text(client_id, text)

        elif msg_type == "audio":
            # Binary audio data from client
            if isinstance(data, bytes) and len(data) > 0:
                conversation_id = connection_manager.get_conversation_id(client_id) or "default"

                await connection_manager.send_state(client_id, ConnectionState.PROCESSING)

                # Transcribe audio
                try:
                    from backend.app.voice.stt import SpeechToText
                    stt = SpeechToText()
                    if not stt.is_ready:
                        await stt.initialize()

                    text = await stt.transcribe(data)
                    if text.strip():
                        # Notify frontend of transcript
                        await connection_manager.send_text(client_id, f"[Transcript: {text}]")

                        # Get AI response
                        response = await engine.chat(
                            message=text,
                            conversation_id=conversation_id,
                        )

                        # Send response
                        await connection_manager.send_text(client_id, response.content, {
                            "conversation_id": conversation_id,
                            "transcript": text,
                        })

                        # Synthesize and stream audio response
                        if settings.TTS_ENGINE and response.content:
                            try:
                                tts = TextToSpeech()
                                if await tts.initialize():
                                    await connection_manager.send_state(client_id, ConnectionState.SPEAKING)
                                    async for chunk in tts.synthesize_stream(response.content):
                                        await connection_manager.send_audio_chunk(client_id, chunk)
                            except Exception as e:
                                logger.warning(f"TTS failed: {e}")

                except Exception as e:
                    logger.error(f"Audio processing failed: {e}")
                    await connection_manager.send_error(client_id, "audio_error", str(e))

                await connection_manager.send_state(client_id, ConnectionState.CONNECTED)

        elif msg_type == "ping":
            pass  # Handled automatically

    # Handle the connection
    await connection_manager.handle_client(websocket, client_id, handle_message)


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
