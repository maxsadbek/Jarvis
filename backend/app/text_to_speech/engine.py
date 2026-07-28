"""Abstract Text-to-Speech Engine.

Defines the interface for all TTS backends.
Supports full synthesis and streaming output.
"""

from __future__ import annotations

import io
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional


@dataclass
class TTSResult:
    """Result from a text-to-speech synthesis."""

    audio_bytes: bytes
    sample_rate: int = 22050
    channels: int = 1
    bit_depth: int = 16
    format: str = "wav"  # "wav" | "mp3" | "ogg"
    duration_seconds: float = 0.0
    text: str = ""
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.audio_bytes) > 0


class TTSEngine(ABC):
    """Abstract base class for text-to-speech engines."""

    def __init__(self) -> None:
        self._initialized = False
        self._voice_name: str = ""

    @abstractmethod
    async def initialize(self) -> bool:
        """Load the TTS voice model and prepare for synthesis."""
        ...

    @abstractmethod
    async def synthesize(self, text: str) -> TTSResult:
        """Synthesize text to audio.

        Args:
            text: Text to convert to speech.

        Returns:
            TTSResult with audio bytes and metadata.
        """
        ...

    async def synthesize_stream(
        self,
        text: str,
        chunk_size_ms: int = 200,
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text and stream audio in chunks.

        Args:
            text: Text to convert to speech.
            chunk_size_ms: Size of each audio chunk in milliseconds.

        Yields:
            Audio data chunks as bytes.
        """
        result = await self.synthesize(text)
        if not result.success:
            return

        frame_size = result.sample_rate * (result.bit_depth // 8) * result.channels
        chunk_frames = int(result.sample_rate * chunk_size_ms / 1000)
        chunk_bytes = chunk_frames * (result.bit_depth // 8) * result.channels

        # Parse WAV header properly (handles variable-length headers)
        audio_data = result.audio_bytes
        if result.format == "wav" and len(result.audio_bytes) > 44:
            try:
                with wave.open(io.BytesIO(result.audio_bytes), "rb") as wav:
                    audio_data = wav.readframes(wav.getnframes())
            except Exception:
                # Fallback: skip 44 bytes for standard WAV header
                audio_data = result.audio_bytes[44:]

        for i in range(0, len(audio_data), chunk_bytes):
            chunk = audio_data[i:i + chunk_bytes]
            if chunk:
                yield chunk

    @property
    def is_ready(self) -> bool:
        """Whether the engine is initialized and ready."""
        return self._initialized

    @property
    def voice_name(self) -> str:
        """Name of the loaded voice."""
        return self._voice_name

    @abstractmethod
    async def close(self) -> None:
        """Release all resources."""
        ...
