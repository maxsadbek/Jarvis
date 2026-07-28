"""Voice Assistant Configuration.

Specialized configuration for the voice interaction pipeline.
Extends the global settings with voice-specific optimizations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VoiceAssistantConfig:
    """Configuration for the voice assistant pipeline."""

    # --- Audio Input ---
    input_sample_rate: int = 16000
    input_channels: int = 1
    input_chunk_duration_ms: int = 100
    input_device: Optional[int] = None  # None = default device

    # --- Voice Activity Detection ---
    vad_enabled: bool = True
    vad_mode: int = 2  # WebRTC VAD aggressiveness (0-3)
    vad_frame_duration_ms: int = 30
    vad_min_speech_duration_ms: int = 200
    vad_min_silence_duration_ms: int = 600
    vad_speech_buffer_seconds: float = 5.0

    # --- Speech-to-Text ---
    stt_engine: str = "faster_whisper"  # "faster_whisper" | "deepgram"
    stt_language: Optional[str] = None  # None = auto-detect
    stt_auto_detect_language: bool = True
    stt_enable_partial_results: bool = True
    stt_partial_interval_ms: int = 2000

    # --- AI Processing ---
    ai_model: Optional[str] = None  # None = use default from settings
    ai_temperature: float = 0.7
    ai_max_tokens: int = 1024
    ai_system_prompt: Optional[str] = None  # None = use default from LLM provider
    ai_stream_response: bool = False

    # --- Text-to-Speech ---
    tts_engine: str = "piper"  # "piper" | "elevenlabs" | "openai"
    tts_voice: Optional[str] = None  # None = use default
    tts_speed: float = 1.0
    tts_chunk_size_ms: int = 200
    tts_stream_audio: bool = True

    # --- Conversation ---
    max_history_messages: int = 20
    enable_memory: bool = True
    enable_context: bool = True
    idle_timeout_seconds: int = 300  # Auto-end session after 5 min idle
    silence_timeout_seconds: int = 30  # Auto-end utterance after 30s silence

    # --- Debug ---
    debug_save_audio: bool = False  # Save audio files for debugging
    debug_audio_dir: str = "data/debug_audio"
    verbose_transcription: bool = False

    @classmethod
    def create_default(cls) -> "VoiceAssistantConfig":
        """Create a default configuration."""
        return cls()
