"""JARVIS Configuration Management.

Central configuration loaded from environment variables and .env file.
Uses pydantic-settings for validation and type coercion.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Locate .env relative to this file, not relative to CWD ─────────────────
# This ensures the .env is found regardless of where uvicorn is launched from.
_config_dir = Path(__file__).resolve().parent  # backend/app/
_env_candidates = [
    _config_dir.parent.parent / ".env",          # Jarvis/.env (project root)
    _config_dir.parent / ".env",                 # backend/.env
    Path.cwd() / ".env",
]
_env_path = next((p for p in _env_candidates if p.exists()), _env_candidates[0])


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_env_path),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "JARVIS"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "Personal AI Assistant"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
    ALLOWED_HOSTS: list[str] = ["*"]

    # --- OpenRouter (LLM) ---
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_FALLBACK_MODEL: str = "anthropic/claude-3-haiku"
    OPENROUTER_MAX_TOKENS: int = 4096
    OPENROUTER_TEMPERATURE: float = 0.7
    OPENROUTER_SITE_URL: Optional[str] = None
    OPENROUTER_SITE_NAME: str = "JARVIS"

    # --- Local LLM (Ollama) ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    USE_LOCAL_LLM: bool = False

    # --- Voice - Speech to Text ---
    STT_ENGINE: str = "faster_whisper"  # "faster_whisper" | "deepgram"
    WHISPER_MODEL_SIZE: str = "base"  # "tiny", "base", "small", "medium", "large-v3"
    WHISPER_DEVICE: str = "auto"  # "cpu", "cuda", "auto"
    WHISPER_COMPUTE_TYPE: str = "auto"  # "float16", "int8", "auto"
    WHISPER_AUTO_DETECT_MIN_PROBABILITY: float = 0.6  # below this -> fall back
    WHISPER_FALLBACK_LANGUAGE: str = "uz"  # used when auto-detect is unreliable
    DEEPGRAM_API_KEY: Optional[str] = None
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    CHUNK_DURATION_MS: int = 100  # Audio chunk size for streaming

    # --- Voice - Text to Speech ---
    TTS_ENGINE: str = "piper"  # "piper" | "elevenlabs" | "openai"
    PIPER_VOICE_MODEL: str = "ru_RU-irina-medium"  # ru reads Cyrillic Uzbek well;
    # tr_TR is the closest official Piper voice for Latin-script Uzbek
    PIPER_VOICE_FALLBACK_MODELS: list[str] = [
        "tr_TR-fettah-medium",
        "en_US-lessac-medium",  # last resort for existing installs
    ]
    PIPER_VOICE_PATH: Optional[str] = None  # Path to .onnx voice file
    PIPER_OUTPUT_SAMPLE_RATE: int = 22050
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"
    OPENAI_TTS_VOICE: str = "alloy"
    TTS_SPEED: float = 1.0

    # --- Wake Word ---
    WAKE_WORD_ENABLED: bool = True
    WAKE_WORD: str = "jarvis"
    WAKE_WORD_SENSITIVITY: float = 0.5
    WAKE_WORD_TIMEOUT: int = 10  # Seconds to listen after wake word
    WAKE_WORD_ENGINE: str = "energy"  # "energy" | "porcupine" | "snowboy"
    PORCUPINE_API_KEY: Optional[str] = None  # Optional, for Picovoice Porcupine

    # --- Voice Manager (prerecorded clips & TTS fallback) ---
    VOICE_MANAGER_ENABLED: bool = True  # Enable the professional voice manager
    VOICE_ASSETS_DIR: str = "assets/voices/jarvis"  # System sound WAV directory
    VOICE_PHRASES_DIR: str = "assets/voices/jarvis/phrases"  # Phrase WAV directory
    VOICE_CACHE_DIR: str = "data/voice_cache"  # Generated TTS cache directory
    VOICE_MASTER_VOLUME: float = 0.8  # Master volume (0.0-1.0)
    VOICE_DEFAULT_FADE_IN_MS: int = 0  # Default fade-in ms for system sounds
    VOICE_DEFAULT_FADE_OUT_MS: int = 0  # Default fade-out ms for system sounds
    VOICE_STARTUP_GREETING_ENABLED: bool = True  # Play greeting on startup
    VOICE_STARTUP_USER_NAME: str = "Максад"  # User name for startup greeting
    VOICE_STARTUP_LANGUAGE: str = "uz"  # Greeting language (ru, en, uz)

    # --- Memory ---
    MEMORY_ENABLED: bool = True
    MEMORY_BACKEND: str = "chroma"  # "chroma" | "json" | "none"
    MEMORY_COLLECTION: str = "jarvis_conversations"
    MEMORY_PERSIST_DIR: str = "data/memory"
    MEMORY_MAX_RESULTS: int = 10
    MEMORY_RELEVANCE_THRESHOLD: float = 0.6
    MEMORY_SHORT_TERM_SIZE: int = 50  # Max messages in short-term buffer
    MEMORY_MAX_CONVERSATIONS: int = 10  # Max active conversations
    MEMORY_FACT_EXTRACTION_ENABLED: bool = True  # Auto-extract facts
    MEMORY_HABIT_LEARNING_ENABLED: bool = True  # Learn user habits
    MEMORY_IMPORTANCE_DECAY_MINUTES: int = 30  # How fast importance decays
    MEMORY_CONTEXT_WINDOW_SECONDS: int = 3600  # 1 hour before summarization

    # --- Authentication ---
    AUTH_ENABLED: bool = False
    JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # --- File System ---
    DATA_DIR: str = "data"
    ALLOWED_FILE_EXTENSIONS: list[str] = [
        ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".csv", ".xml", ".html", ".css", ".scss",
        ".jpg", ".jpeg", ".png", ".gif", ".svg",
        ".pdf", ".doc", ".docx",
        ".mp3", ".wav", ".ogg",
        ".zip", ".tar", ".gz",
    ]
    MAX_FILE_SIZE_MB: int = 50

    # --- Tool System ---
    TOOLS_ENABLED: bool = True
    ENABLED_TOOLS: list[str] = [
        "web_search",
        "file_ops",
        "code_exec",
        "system_ctl",
        "browser",
        "command_runner",
        # Desktop control modules
        "app_control",
        "system_control",
        "file_control",
        "media_control",
        "developer",
    ]

    # --- Security & Automation ---
    SECURITY_AUDIT_ENABLED: bool = True  # Audit all tool executions
    SECURITY_MAX_EXECUTION_TIME: int = 60  # Max seconds for tool execution
    SECURITY_REQUIRE_CONFIRMATION: bool = True  # Require confirm for risky actions
    SECURITY_MAX_CONCURRENT_TOOLS: int = 5  # Max parallel tool executions
    SECURITY_COMMAND_SANDBOX_ENABLED: bool = True  # Sandbox command execution
    AUTOMATION_ENABLED: bool = True  # Enable task automation engine
    AUTOMATION_MAX_TASKS: int = 50  # Max stored automation tasks
    AUTOMATION_MAX_STEPS_PER_TASK: int = 20  # Max steps per task

    # --- Plugin System ---
    PLUGINS_ENABLED: bool = True
    PLUGINS_DIR: str = "plugins"
    ENABLED_PLUGINS: list[str] = []

    # --- Web Search ---
    SEARCH_ENGINE: str = "duckduckgo"  # "duckduckgo" | "google" | "bing"
    SEARCH_MAX_RESULTS: int = 5
    SEARCH_TIMEOUT: int = 10

    def get_data_path(self, subpath: str = "") -> Path:
        """Get absolute path to a data directory."""
        base = Path(self.DATA_DIR)
        if subpath:
            base = base / subpath
        base.mkdir(parents=True, exist_ok=True)
        return base.absolute()

    def get_model_path(self) -> Path:
        """Get path for local AI models."""
        path = Path("data/models")
        path.mkdir(parents=True, exist_ok=True)
        return path.absolute()

    @property
    def is_voice_enabled(self) -> bool:
        """Check if voice system is configured."""
        return self.STT_ENGINE is not None or self.TTS_ENGINE is not None

    @property
    def is_llm_configured(self) -> bool:
        """Check if any LLM provider is configured."""
        if self.USE_LOCAL_LLM:
            return True
        return self.OPENROUTER_API_KEY is not None


# Global settings instance
settings = Settings()

# Ensure data directories exist
settings.get_data_path("memory")
settings.get_data_path("voice")
settings.get_data_path("logs")
