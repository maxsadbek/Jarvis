"""JARVIS AI Assistant - Main Application Entry Point.

FastAPI application with WebSocket support for real-time voice/chat.
Run with: uvicorn main:app --reload

Production features:
- Structured logging with rotation (api, voice, performance, crash)
- Health monitoring endpoint
- WebSocket real-time communication
- Voice pipeline integration
- Voice Manager (prerecorded clips, smart phrase matching, TTS fallback)
- Tool system with permission-based access
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, Query, Request, HTTPException
from loguru import logger

from backend.app.api.middleware import setup_middleware
from backend.app.api.websocket import ConnectionManager
from backend.app.config import settings
from backend.app.core.engine import AIEngine
from backend.app.services import MessageHandler
from backend.app.services.logging_service import LoggingService, LogCategory
from backend.app.api.routes import chat as chat_routes, voice as voice_routes, memory as memory_routes
from backend.app.tools.routes import router as tools_router
from backend.app.assistant_core import VoicePipeline, PipelineConfig, VoiceAssistantConfig
from backend.app.voice import VoiceManager


# --- Global Service Locator ---
# Cleaner than monkey-patching; use app.state for request-scoped access.

_engine: AIEngine | None = None
_connection_manager: ConnectionManager | None = None
_voice_pipeline: VoicePipeline | None = None
_voice_manager: VoiceManager | None = None
_logging_service: LoggingService | None = None


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
    global _engine, _connection_manager, _voice_pipeline, _voice_manager

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")

    # 0. Initialize logging service
    _logging_service = LoggingService()
    _logging_service.initialize(level=settings.LOG_LEVEL)
    _logging_service.log_security("system_start", f"{settings.APP_NAME} v{settings.APP_VERSION} starting")

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

    # 3. Initialize Voice Manager (prerecorded clips + TTS fallback)
    if settings.VOICE_MANAGER_ENABLED:
        # Get TTS engine from pipeline if available
        tts_engine = None
        if _voice_pipeline and hasattr(_voice_pipeline, '_tts'):
            tts_engine = _voice_pipeline._tts

        # Resolve voice assets directory (handle both absolute and relative paths)
        assets_dir = Path(settings.VOICE_ASSETS_DIR)
        if not assets_dir.is_absolute():
            assets_dir = settings.get_data_path() / settings.VOICE_ASSETS_DIR

        _voice_manager = VoiceManager(
            assets_dir=assets_dir,
            phrases_dir=Path(settings.VOICE_PHRASES_DIR),
            cache_dir=Path(settings.VOICE_CACHE_DIR),
            tts_engine=tts_engine,
        )
        await _voice_manager.initialize()

        # Wire voice events into the pipeline
        if _voice_pipeline:
            _voice_pipeline.set_voice_manager(_voice_manager)

        # Play startup sequence (non-blocking, with delay for TTS readiness)
        if settings.VOICE_STARTUP_GREETING_ENABLED:
            async def _delayed_startup():
                # Wait for voice pipeline TTS to be ready (up to 5 seconds)
                for _ in range(10):
                    if (_voice_pipeline and _voice_pipeline._tts
                            and _voice_pipeline._tts.is_ready):
                        break
                    await asyncio.sleep(0.5)
                await _voice_manager.play_startup_sequence(
                    user_name=settings.VOICE_STARTUP_USER_NAME,
                )
            asyncio.create_task(_delayed_startup())

        logger.info("Voice Manager ready")
    else:
        logger.info("Voice Manager disabled")

    # 4. Initialize WebSocket manager
    _connection_manager = ConnectionManager()

    # Store in app state for route injection
    app.state.engine = _engine
    app.state.connection_manager = _connection_manager
    app.state.voice_pipeline = _voice_pipeline
    app.state.voice_manager = _voice_manager
    app.state.logging_service = _logging_service

    logger.info(f"{settings.APP_NAME} is ready! 🚀")
    _logging_service.log_security("system_ready", f"{settings.APP_NAME} initialized successfully")
    yield

    # Shutdown
    logger.info("Shutting down...")
    if _logging_service:
        _logging_service.log_security("system_shutdown", "Application shutting down")

    # Play shutdown sequence first (non-blocking, with timeout)
    if _voice_manager:
        try:
            await asyncio.wait_for(
                _voice_manager.play_shutdown_sequence(),
                timeout=5.0,
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"Shutdown sequence incomplete: {e}")
        finally:
            await _voice_manager.shutdown()

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
app.dependency_overrides[memory_routes.get_engine] = get_engine

app.include_router(chat_routes.router)
app.include_router(voice_routes.router)
app.include_router(memory_routes.router)
app.include_router(tools_router)


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


# --- Voice Manager REST endpoints ---

@app.get("/api/voice/manager/status")
async def voice_manager_status() -> dict:
    """Get Voice Manager status and diagnostics."""
    if not _voice_manager:
        return {"status": "disabled", "message": "Voice Manager not initialized"}
    return _voice_manager.get_diagnostics()


@app.post("/api/voice/manager/play")
async def voice_manager_play(clip_name: str, category: str = "jarvis", volume: float = 0.8):
    """Play a specific voice clip by name."""
    if not _voice_manager:
        raise HTTPException(status_code=503, detail="Voice Manager not available")
    success = await _voice_manager.play(clip_name, category=category, volume=volume)
    return {"success": success}


@app.post("/api/voice/manager/speak")
async def voice_manager_speak(text: str, volume: float = 0.8):
    """Speak text via TTS (with phrase matching)."""
    if not _voice_manager:
        raise HTTPException(status_code=503, detail="Voice Manager not available")
    success = await _voice_manager.speak(text, volume=volume)
    return {"success": success}


@app.post("/api/voice/manager/event")
async def voice_manager_event(event: str):
    """Play a voice event sound (e.g., startup, error, connected)."""
    if not _voice_manager:
        raise HTTPException(status_code=503, detail="Voice Manager not available")
    success = await _voice_manager.play_event(event)
    return {"success": success}


@app.post("/api/voice/manager/stop")
async def voice_manager_stop():
    """Stop all current voice playback."""
    if _voice_manager:
        await _voice_manager.stop()
    return {"success": True}


@app.post("/api/voice/manager/reload")
async def voice_manager_reload():
    """Hot-reload all voice clips from disk."""
    if not _voice_manager:
        raise HTTPException(status_code=503, detail="Voice Manager not available")
    success = await _voice_manager.reload()
    return {"success": success, "clip_count": _voice_manager.loaded_count}


@app.get("/api/voice/manager/clips")
async def voice_manager_clips(category: str | None = None):
    """List all loaded voice clips."""
    if not _voice_manager:
        return []
    return _voice_manager.get_all_clips(category=category)


@app.get("/api/voice/manager/match")
async def voice_manager_match(text: str):
    """Test phrase matching against the voice library."""
    if not _voice_manager:
        return {"matched": False, "clip_name": None}
    clip_name = _voice_manager.match_phrase(text)
    return {
        "matched": clip_name is not None,
        "clip_name": clip_name,
        "clip_info": _voice_manager.get_clip_info(clip_name) if clip_name else None,
    }


# --- Diagnostics / Startup Progress Endpoint ---

@app.get("/api/diagnostics")
async def system_diagnostics() -> dict:
    """Comprehensive system diagnostics.

    Returns the status of every subsystem for the startup splash screen.
    Called by Electron after /api/health returns 'healthy'.
    """
    import subprocess
    import socket

    result = {
        "status": "running",
        "checks": {},
        "all_systems_operational": False,
    }

    # --- Backend ---
    result["checks"]["backend"] = {
        "name": "Backend Service",
        "status": "ready",
        "message": "Серверная часть работает" if settings.APP_NAME == "JARVIS" else "Backend operational",
    }

    # --- LLM / AI Model ---
    if _engine:
        if _engine.is_llm_ready:
            result["checks"]["llm"] = {
                "name": "AI Model",
                "status": "ready",
                "message": f"Модель {settings.OPENROUTER_MODEL} загружена" if settings.APP_NAME == "JARVIS" else f"Model {settings.OPENROUTER_MODEL} loaded",
            }
        else:
            result["checks"]["llm"] = {
                "name": "AI Model",
                "status": "warning",
                "message": "Модель AI не подключена (проверьте API ключ)" if settings.APP_NAME == "JARVIS" else "AI model not connected (check API key)",
            }
    else:
        result["checks"]["llm"] = {"name": "AI Model", "status": "waiting", "message": "Engine initializing..."}

    # --- Memory ---
    mem_ok = _engine and _engine.memory is not None
    result["checks"]["memory"] = {
        "name": "Memory System",
        "status": "ready" if mem_ok else "warning",
        "message": "Память загружена" if mem_ok else "Память не инициализирована",
    }

    # --- Tools ---
    tools_count = len(_engine._tool_registry.tools) if _engine and _engine._tool_registry else 0
    result["checks"]["tools"] = {
        "name": "Tool System",
        "status": "ready" if tools_count > 0 else "warning",
        "message": f"{tools_count} инструментов загружено" if tools_count > 0 else "Инструменты не загружены",
        "tools": list(_engine._tool_registry.tools.keys()) if _engine and _engine._tool_registry else [],
    }

    # --- Internet ---
    internet_ok = False
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        internet_ok = True
    except (OSError, socket.timeout):
        pass
    result["checks"]["internet"] = {
        "name": "Internet Connection",
        "status": "ready" if internet_ok else "error",
        "message": "Интернет подключён" if internet_ok else "Нет подключения к интернету",
    }

    # --- Microphone ---
    mic_ok = False
    mic_name = ""
    try:
        import sounddevice as sd  # type: ignore[import-untyped]
        devices = sd.query_devices()
        input_devices = [d for d in devices if d["max_input_channels"] > 0]
        if input_devices:
            default_mic = sd.default.device[0]
            if default_mic is not None:
                mic_info = sd.query_devices(default_mic)
                mic_name = mic_info["name"]
                mic_ok = True
            else:
                mic_info = sd.query_devices(input_devices[0]["index"])
                mic_name = mic_info["name"]
                mic_ok = True
    except (ImportError, Exception):
        pass
    result["checks"]["microphone"] = {
        "name": "Microphone",
        "status": "ready" if mic_ok else "error",
        "message": f"Микрофон '{mic_name}' работает" if mic_ok else "Микрофон не обнаружен",
        "device_name": mic_name if mic_ok else "",
    }

    # --- Speakers ---
    speaker_ok = False
    speaker_name = ""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        output_devices = [d for d in devices if d["max_output_channels"] > 0]
        if output_devices:
            default_spk = sd.default.device[1]
            if default_spk is not None:
                spk_info = sd.query_devices(default_spk)
                speaker_name = spk_info["name"]
                speaker_ok = True
            else:
                spk_info = sd.query_devices(output_devices[0]["index"])
                speaker_name = spk_info["name"]
                speaker_ok = True
    except (ImportError, Exception):
        pass
    result["checks"]["speakers"] = {
        "name": "Speakers",
        "status": "ready" if speaker_ok else "error",
        "message": f"Динамики '{speaker_name}' работают" if speaker_ok else "Динамики не обнаружены",
        "device_name": speaker_name if speaker_ok else "",
    }

    # --- Voice Pipeline ---
    vp_ok = _voice_pipeline is not None and _voice_pipeline.is_ready
    result["checks"]["voice_pipeline"] = {
        "name": "Voice Pipeline",
        "status": "ready" if vp_ok else "warning",
        "message": "Голосовой конвейер готов" if vp_ok else "Голосовой конвейер не инициализирован",
    }

    # --- Voice Manager ---
    vm_ok = _voice_manager is not None and _voice_manager.is_ready
    vm_clips = _voice_manager.loaded_count if _voice_manager else 0
    result["checks"]["voice_manager"] = {
        "name": "Voice Manager",
        "status": "ready" if vm_ok else "warning",
        "message": f"{vm_clips} голосовых клипов загружено" if vm_ok else "Голосовой менеджер не инициализирован",
        "clip_count": vm_clips,
        "clips": _voice_manager.loaded_clips if _voice_manager else [],
    }

    # --- Configuration ---
    result["checks"]["configuration"] = {
        "name": "Configuration",
        "status": "ready",
        "message": "Конфигурация загружена",
    }

    # Determine overall status
    all_ready = all(
        check["status"] in ("ready", "warning")
        for check in result["checks"].values()
    )
    result["all_systems_operational"] = all_ready

    return result


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
            "diagnostics": "/api/diagnostics",
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
