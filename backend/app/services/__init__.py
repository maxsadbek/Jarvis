"""Services Module.

Contains service-layer logic extracted from route handlers and main.py
to promote separation of concerns and testability.

Sub-modules:
    websocket_handler.py  - WebSocket message routing
    startup.py            - Windows background service, auto-start, health monitor
    logging_service.py    - Structured logging with rotation and categories
"""

from .websocket_handler import MessageHandler, MessageHandlerError, EngineNotReadyError
from .startup import (
    BackendProcessManager,
    StartupConfig,
    WindowsStartupManager,
    VoiceGreetingService,
    run_service,
)
from .logging_service import LoggingService, LogCategory, logging_service

__all__ = [
    # WebSocket
    "MessageHandler",
    "MessageHandlerError",
    "EngineNotReadyError",
    # Windows Startup
    "BackendProcessManager",
    "StartupConfig",
    "WindowsStartupManager",
    "VoiceGreetingService",
    "run_service",
    # Logging
    "LoggingService",
    "LogCategory",
    "logging_service",
]
