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
    COMMAND_RUNNER = "command_runner"


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
    type: str = "conversation"  # conversation | fact | preference | habit | summary
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = 0.0
    importance: float = 0.5  # 0.0 (trivial) to 1.0 (critical)
    access_count: int = 0  # How many times this was retrieved
    last_accessed: Optional[datetime] = None
    category: str = "general"  # general | personal | work | code | system | preference


class UserPreference(BaseModel):
    """A stored user preference."""
    key: str
    value: Any
    category: str = "general"  # general | voice | appearance | privacy | ai
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class UserHabit(BaseModel):
    """A learned user habit or pattern."""
    id: str
    pattern: str  # Description of the detected pattern
    confidence: float = 0.0  # 0.0 (unsure) to 1.0 (certain)
    frequency: int = 1  # How many times this pattern was observed
    category: str = "general"  # general | communication | work | schedule | coding
    first_observed: datetime = Field(default_factory=datetime.now)
    last_observed: datetime = Field(default_factory=datetime.now)
    evidence: list[str] = Field(default_factory=list)  # Example interactions


class ImportantFact(BaseModel):
    """An important fact extracted from conversation."""
    id: str
    fact: str  # The extracted fact
    source: str = "conversation"  # conversation | preference | system
    confidence: float = 0.0
    importance: float = 0.5
    category: str = "general"  # personal | work | preference | contact | code
    verified: bool = False  # Whether the user confirmed this fact
    timestamp: datetime = Field(default_factory=datetime.now)
    context: Optional[str] = None  # Surrounding conversation context
    conversation_id: Optional[str] = None


class ConversationSummary(BaseModel):
    """A summary of a conversation session."""
    id: str
    conversation_id: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    sentiment: Optional[str] = None  # positive | neutral | negative
    message_count: int = 0
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: datetime = Field(default_factory=datetime.now)
    token_count: int = 0


class MemoryQuery(BaseModel):
    """A query to the memory system."""
    query: str
    limit: int = 10
    threshold: float = 0.5
    categories: Optional[list[str]] = None
    memory_types: Optional[list[str]] = None
    time_range_hours: Optional[int] = None
    min_importance: Optional[float] = None


class MemorySearchResult(BaseModel):
    """Result from a memory search with context."""
    items: list[MemoryItem] = Field(default_factory=list)
    total_results: int = 0
    query_time_ms: float = 0.0
    strategies_used: list[str] = Field(default_factory=list)


class RiskLevel(str, Enum):
    """Risk level of an action."""
    SAFE = "safe"          # Read-only, no side effects
    LOW = "low"            # Minor side effects (writing files)
    MEDIUM = "medium"       # System modifications (installing, deleting)
    HIGH = "high"           # Destructive actions (formatting, shutdown)
    CRITICAL = "critical"   # Irreversible actions


class PermissionDecision(str, Enum):
    """Decision on a permission request."""
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_PASSWORD = "requires_password"


class PermissionRule(BaseModel):
    """A rule controlling tool permissions."""
    id: str
    tool_name: str
    action: Optional[str] = None  # None = applies to all actions
    risk_level: RiskLevel = RiskLevel.SAFE
    decision: PermissionDecision = PermissionDecision.ALLOWED
    auto_confirm: bool = False  # Auto-confirm without asking
    max_calls_per_minute: int = 0  # 0 = unlimited
    created_at: datetime = Field(default_factory=datetime.now)
    reason: Optional[str] = None


class AuditEntry(BaseModel):
    """An audit log entry for tool execution."""
    id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tool_name: str
    action: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.SAFE
    permission_decision: PermissionDecision = PermissionDecision.ALLOWED
    status: str = "pending"  # "pending" | "running" | "completed" | "error" | "denied"
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    user_confirmed: bool = False
    session_id: Optional[str] = None


class AutomationTask(BaseModel):
    """A scheduled or repeatable automation task."""
    id: str
    name: str
    description: Optional[str] = None
    steps: list[TaskStep] = Field(default_factory=list)
    schedule: Optional[str] = None  # Cron expression
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    total_runs: int = 0
    tags: list[str] = Field(default_factory=list)


class TaskStep(BaseModel):
    """A single step in an automation task."""
    id: str
    tool_name: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    timeout_seconds: int = 30
    retry_on_failure: bool = False
    max_retries: int = 0
    depends_on: list[str] = Field(default_factory=list)  # Step IDs this depends on


class ExecutionSandbox(BaseModel):
    """Sandbox configuration for safe execution."""
    allowed_directories: list[str] = Field(default_factory=list)
    blocked_directories: list[str] = Field(default_factory=list)
    allowed_commands: list[str] = Field(default_factory=list)
    blocked_commands: list[str] = Field(default_factory=list)
    max_processes: int = 5
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    timeout_seconds: int = 30
    network_access: bool = False


class ToolCall(BaseModel):
    """A tool call made by the AI."""
    id: str
    name: ToolName
    arguments: dict[str, Any]
    result: Optional[str] = None
    status: str = "pending"  # "pending" | "running" | "completed" | "error" | "denied"
    error: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False
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
