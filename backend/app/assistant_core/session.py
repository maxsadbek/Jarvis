"""Voice Session Manager.

Manages the lifecycle of a voice interaction session.
Tracks state, timing, and user context for each session.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger


class SessionState(str, Enum):
    """State of a voice interaction session."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING_SPEECH = "processing_speech"
    WAITING_FOR_AI = "waiting_for_ai"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ENDED = "ended"


@dataclass
class Utterance:
    """A single user utterance in a voice session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    audio_bytes: bytes = field(default_factory=bytes)
    language: str = "en"
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 0.0
    is_partial: bool = False
    is_final: bool = False
    response_text: str = ""
    response_audio: bytes = field(default_factory=bytes)
    processing_time_ms: float = 0.0

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.timestamp


@dataclass
class VoiceSession:
    """Represents a complete voice interaction session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    state: SessionState = SessionState.IDLE
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    utterances: list[Utterance] = field(default_factory=list)
    current_utterance: Optional[Utterance] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_activity

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def utterance_count(self) -> int:
        return len(self.utterances)

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "id": self.id,
            "state": self.state.value,
            "conversation_id": self.conversation_id,
            "utterance_count": self.utterance_count,
            "duration_seconds": self.duration_seconds,
            "idle_seconds": self.idle_seconds,
            "is_active": self.is_active,
        }


class SessionManager:
    """Manages multiple voice sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}

    def create_session(self, conversation_id: Optional[str] = None) -> VoiceSession:
        """Create a new voice session.

        Args:
            conversation_id: Optional existing conversation ID to attach.

        Returns:
            The new VoiceSession.
        """
        session = VoiceSession(
            conversation_id=conversation_id or str(uuid.uuid4()),
        )
        self._sessions[session.id] = session
        logger.info(f"Voice session created: {session.id[:8]}...")
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: Optional[str] = None) -> VoiceSession:
        """Get an existing session or create a new one."""
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if session.is_active:
                return session
        return self.create_session()

    def end_session(self, session_id: str) -> None:
        """End a session gracefully."""
        session = self._sessions.get(session_id)
        if session:
            session.state = SessionState.ENDED
            session.is_active = False
            logger.info(f"Voice session ended: {session_id[:8]}...")

    def get_active_sessions(self) -> list[VoiceSession]:
        """Get all active sessions."""
        return [s for s in self._sessions.values() if s.is_active]

    def cleanup_stale_sessions(self, max_idle_seconds: int = 600) -> int:
        """End sessions that have been idle too long.

        Args:
            max_idle_seconds: Maximum idle time before auto-ending.

        Returns:
            Number of sessions cleaned up.
        """
        count = 0
        now = time.time()
        for session in list(self._sessions.values()):
            if session.is_active and (now - session.last_activity) > max_idle_seconds:
                session.state = SessionState.ENDED
                session.is_active = False
                count += 1
        return count

    @property
    def active_count(self) -> int:
        return len(self.get_active_sessions())

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": self.active_count,
            "stale_sessions": len(self._sessions) - self.active_count,
        }
