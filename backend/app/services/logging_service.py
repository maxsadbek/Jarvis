"""JARVIS Structured Logging Service.

Provides:
- Structured JSON logs for all subsystems
- Automatic log rotation with size/time limits
- Crash log capture with full stack traces
- Performance metrics logging
- Voice system logging
- API request/response logging
- Log level management at runtime

Log directory structure:
  data/logs/
    jarvis_{date}.log          - Main application log
    api_{date}.log             - API request/response log
    voice_{date}.log           - Voice pipeline log
    performance_{date}.log     - Performance metrics
    crash_{date}.log           - Crash/error reports
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class LogCategory(str, Enum):
    """Log categories for routing to different files."""
    SYSTEM = "system"
    API = "api"
    VOICE = "voice"
    PERFORMANCE = "performance"
    CRASH = "crash"
    MEMORY = "memory"
    TOOLS = "tools"
    SECURITY = "security"
    DEBUG = "debug"


class LoggingService:
    """Centralized logging with rotation, categories, and structured output."""

    _instance: Optional["LoggingService"] = None
    _initialized = False

    def __new__(cls) -> "LoggingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._log_dir = Path("data/logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Session ID for correlating logs
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Performance counters
        self._request_count = 0
        self._error_count = 0
        self._start_time = time.time()

    def initialize(self, log_dir: Optional[str] = None, level: str = "INFO") -> None:
        """Initialize the logging system with file sinks.

        Args:
            log_dir: Custom log directory.
            level: Log level (TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL).
        """
        if log_dir:
            self._log_dir = Path(log_dir)
            self._log_dir.mkdir(parents=True, exist_ok=True)

        # Remove default handler
        logger.remove()

        # Console handler (structured for production)
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:HH:mm:ss.SSS}</green> | "
                "<level>{level:<7}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            level=level,
            colorize=True,
        )

        # Main application log
        logger.add(
            str(self._log_dir / "jarvis_{time:YYYY-MM-DD}.log"),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}:{function}:{line} | {message}",
            rotation="10 MB",
            retention="30 days",
            compression="gz",
            level=level,
        )

        # API log
        logger.add(
            str(self._log_dir / "api_{time:YYYY-MM-DD}.log"),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {message}",
            rotation="10 MB",
            retention="14 days",
            compression="gz",
            level="INFO",
            filter=lambda record: record["extra"].get("category") == LogCategory.API,
        )

        # Voice log
        logger.add(
            str(self._log_dir / "voice_{time:YYYY-MM-DD}.log"),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {message}",
            rotation="10 MB",
            retention="14 days",
            compression="gz",
            level="DEBUG",
            filter=lambda record: record["extra"].get("category") == LogCategory.VOICE,
        )

        # Performance log
        logger.add(
            str(self._log_dir / "performance_{time:YYYY-MM-DD}.log"),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
            rotation="5 MB",
            retention="7 days",
            compression="gz",
            level="INFO",
            filter=lambda record: record["extra"].get("category") == LogCategory.PERFORMANCE,
        )

        # Crash/Error log
        logger.add(
            str(self._log_dir / "crash_{time:YYYY-MM-DD}.log"),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {message}",
            rotation="5 MB",
            retention="90 days",
            compression="gz",
            level="ERROR",
            filter=lambda record: record["extra"].get("category") in (LogCategory.CRASH, None),
            backtrace=True,
            diagnose=True,
        )

        # Security audit log
        logger.add(
            str(self._log_dir / "security_{time:YYYY-MM-DD}.log"),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
            rotation="10 MB",
            retention="90 days",
            compression="gz",
            level="INFO",
            filter=lambda record: record["extra"].get("category") == LogCategory.SECURITY,
        )

        self._log_initialized()
        logger.info(f"Logging system initialized (session: {self._session_id})")

    def _log_initialized(self) -> None:
        """Log system initialization info."""
        logger.info("=" * 60)
        logger.info(f"JARVIS v0.1.0 - Session {self._session_id}")
        logger.info(f"Platform: {platform.system()} {platform.release()}")
        logger.info(f"Python: {sys.version}")
        logger.info(f"Log dir: {self._log_dir}")
        logger.info("=" * 60)

    # ─── Convenience Methods ───────────────────────────────────────────────

    def log_api(self, method: str, path: str, status: int, duration_ms: float, **extra: Any) -> None:
        """Log an API request.

        Args:
            method: HTTP method.
            path: Request path.
            status: HTTP status code.
            duration_ms: Request duration in milliseconds.
            **extra: Additional context.
        """
        self._request_count += 1
        extra_data = {
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": f"{duration_ms:.1f}",
            "request_number": self._request_count,
            **extra,
        }
        logger.bind(category=LogCategory.API).info(
            f"[API] {method} {path} → {status} ({duration_ms:.0f}ms) {json.dumps(extra_data) if extra else ''}"
        )

    def log_voice(self, event: str, details: str = "", **extra: Any) -> None:
        """Log a voice pipeline event.

        Args:
            event: Voice event name (e.g., 'wake_word_detected', 'transcription_complete').
            details: Human-readable details.
            **extra: Additional context.
        """
        logger.bind(category=LogCategory.VOICE).info(
            f"[VOICE] {event}: {details} {json.dumps(extra) if extra else ''}"
        )

    def log_performance(self, operation: str, duration_ms: float, **metrics: Any) -> None:
        """Log a performance metric.

        Args:
            operation: Operation name (e.g., 'llm_chat', 'stt_transcribe').
            duration_ms: Duration in milliseconds.
            **metrics: Additional performance metrics.
        """
        logger.bind(category=LogCategory.PERFORMANCE).info(
            json.dumps({
                "operation": operation,
                "duration_ms": round(duration_ms, 2),
                "timestamp": datetime.now().isoformat(),
                **metrics,
            })
        )

    def log_crash(self, error: Exception, context: Optional[str] = None) -> None:
        """Log a crash/error with full stack trace.

        Args:
            error: The exception that occurred.
            context: Optional context about what was happening.
        """
        self._error_count += 1
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        crash_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": tb,
            "context": context,
            "error_count": self._error_count,
            "session_id": self._session_id,
        }
        logger.bind(category=LogCategory.CRASH).error(
            f"[CRASH #{self._error_count}] {context or ''}\n{tb}"
        )
        # Write crash report file
        crash_file = self._log_dir / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._error_count}.json"
        try:
            crash_file.write_text(json.dumps(crash_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def log_security(self, event: str, details: str = "", **extra: Any) -> None:
        """Log a security event.

        Args:
            event: Security event name.
            details: Event details.
            **extra: Additional context.
        """
        logger.bind(category=LogCategory.SECURITY).info(
            f"[SECURITY] {event}: {details} {json.dumps(extra) if extra else ''}"
        )

    def log_tool(self, tool_name: str, action: str, status: str, duration_ms: float, **extra: Any) -> None:
        """Log a tool execution.

        Args:
            tool_name: Tool name.
            action: Action performed.
            status: Execution status.
            duration_ms: Duration in milliseconds.
            **extra: Additional context.
        """
        logger.bind(category=LogCategory.TOOLS).info(
            f"[TOOL] {tool_name}.{action} → {status} ({duration_ms:.0f}ms) {json.dumps(extra) if extra else ''}"
        )

    # ─── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get logging statistics."""
        uptime = time.time() - self._start_time
        return {
            "session_id": self._session_id,
            "uptime_seconds": round(uptime),
            "requests_logged": self._request_count,
            "errors_logged": self._error_count,
            "log_dir": str(self._log_dir),
            "log_size_mb": self._get_log_dir_size(),
        }

    def _get_log_dir_size(self) -> float:
        """Get total size of log files in MB."""
        total = 0
        try:
            for f in self._log_dir.glob("*.log*"):
                total += f.stat().st_size
            return round(total / (1024 * 1024), 2)
        except Exception:
            return 0.0

    def get_recent_logs(self, lines: int = 50, level: str = "INFO") -> list[str]:
        """Get recent log lines from the main log file.

        Args:
            lines: Number of recent lines to return.
            level: Minimum log level.

        Returns:
            List of recent log lines.
        """
        log_file = self._log_dir / f"jarvis_{datetime.now().strftime('%Y-%m-%d')}.log"
        if not log_file.exists():
            return ["No logs available"]

        try:
            all_lines = log_file.read_text(encoding="utf-8").strip().split("\n")
            return all_lines[-lines:]
        except Exception:
            return ["Error reading logs"]


# Global logging service instance
logging_service = LoggingService()
