"""Pydantic schemas for JARVIS data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Enums ---

class MessageRole(str, Enum):
    """Role of a message sender."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MessageType(str, Enum):
    """Type of message content."""
    TEXT = "text"
    VOICE = "voice"
    COMMAND = "command"
    SYSTEM = "system"
    ERROR = "error"
    IMAGE = "image"
    FILE = "file"
    CODE = "code"


class ToolName(str, Enum):
    """Available tool names."""
    WEB_SEARCH = "web_search"
    FILE_OPS = "file_ops"
    CODE_EXEC = "code_exec"
    SYSTEM_CTL = "system_ctl"
    BROWSER = "browser"
    MEMORY = "memory"


class ConnectionState(str, Enum):
    """WebSocket connection state."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    DISCONNECTED = "disconnected"


# --- Message Models ---

class Message(BaseModel):
    """A single message in a conversation."""
    id: str = Field(default_factory=lambda: datetime.now().isoformat())
    role: MessageRole
    type: MessageType = MessageType.TEXT
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class Conversation(BaseModel):
    """A conversation session."""
    id: str = Field(default_factory=lambda: datetime.now().isoformat())
    title: str = "New Conversation"
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- WebSocket Messages ---

class WSMessage(BaseModel):
    """WebSocket message envelope."""
    type: str  # "transcript", "response", "error", "state", "audio", "command"
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class TranscriptMessage(WSMessage):
    """Voice transcript received from client."""
    type: str = "transcript"
    data: dict[str, Any]  # {"text": "...", "is_final": bool, "language": "..."}


class ResponseMessage(WSMessage):
    """AI response to send to client."""
    type: str = "response"
    data: dict[str, Any]  # {"text": "...", "audio": "...", "tokens_used": int}


class AudioChunkMessage(WSMessage):
    """Binary audio chunk for streaming TTS."""
    type: str = "audio"
    data: dict[str, Any]  # {"chunk": "...", "format": "wav", "sample_rate": 22050}


class StateMessage(WSMessage):
    """Connection state update."""
    type: str = "state"
    data: dict[str, Any]  # {"state": "listening" | "processing" | "speaking"}


class CommandMessage(WSMessage):
    """Command from the client."""
    type: str = "command"
    data: dict[str, Any]  # {"action": "...", "params": {...}}


class ErrorMessage(WSMessage):
    """Error message."""
    type: str = "error"
    data: dict[str, Any]  # {"code": "...", "message": "..."}


# --- API Request/Response Models ---

class ChatRequest(BaseModel):
    """Request for text-based chat."""
    message: str
    conversation_id: Optional[str] = None
    stream: bool = False
    model: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat completion."""
    message: Message
    conversation_id: str
    tokens_used: int = 0
    processing_time_ms: float = 0.0


class VoiceConfig(BaseModel):
    """Voice configuration settings."""
    stt_engine: str = "faster_whisper"
    tts_engine: str = "piper"
    wake_word_enabled: bool = True
    wake_word: str = "jarvis"
    tts_speed: float = 1.0
    sample_rate: int = 16000


class MemoryItem(BaseModel):
    """An item stored in long-term memory."""
    id: str
    content: str
    type: str = "conversation"
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = 0.0


class ToolCall(BaseModel):
    """A tool call made by the AI."""
    id: str
    name: ToolName
    arguments: dict[str, Any]
    result: Optional[str] = None
    status: str = "pending"  # "pending" | "running" | "completed" | "error"
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# --- System Status Models ---

class SystemStatus(BaseModel):
    """Overall system status."""
    app_name: str = "JARVIS"
    app_version: str = "0.1.0"
    status: str = "running"
    llm_connected: bool = False
    llm_model: Optional[str] = None
    stt_ready: bool = False
    tts_ready: bool = False
    memory_ready: bool = False
    tools_loaded: list[str] = Field(default_factory=list)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    uptime_seconds: float = 0.0


class SettingsUpdate(BaseModel):
    """Update settings request."""
    settings: dict[str, Any]
