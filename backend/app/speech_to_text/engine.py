"""Abstract Speech-to-Text Engine.

Defines the interface for all STT backends.
Supports both file-based and streaming transcription.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional
from pathlib import Path


@dataclass
class STTResult:
    """Result from a speech-to-text transcription."""

    text: str
    confidence: float = 0.0
    language: str = "en"
    duration_seconds: float = 0.0
    segments: list[dict] = field(default_factory=list)
    is_partial: bool = False
    error: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()

    @property
    def success(self) -> bool:
        return self.error is None and not self.is_empty


class STTEngine(ABC):
    """Abstract base class for speech-to-text engines."""

    def __init__(self) -> None:
        self._initialized = False
        self._model_name: str = ""

    @abstractmethod
    async def initialize(self) -> bool:
        """Load the STT model and prepare for transcription."""
        ...

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> STTResult:
        """Transcribe audio bytes to text.

        Args:
            audio_data: Raw PCM audio bytes (16-bit, mono).
            sample_rate: Sample rate of the audio.
            language: Optional language code override (e.g., "en", "fr").

        Returns:
            STTResult with transcribed text and metadata.
        """
        ...

    @abstractmethod
    async def transcribe_file(
        self,
        file_path: str | Path,
        language: Optional[str] = None,
    ) -> STTResult:
        """Transcribe an audio file."""
        ...

    async def transcribe_stream(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        sample_rate: int = 16000,
    ) -> AsyncGenerator[STTResult, None]:
        """Transcribe streaming audio, yielding partial results.

        Default implementation buffers audio and processes in chunks.
        Override for true streaming transcription.
        """
        buffer = bytearray()
        chunk_duration_frames = sample_rate * 4  # 4-second chunks

        async for chunk in audio_generator:
            buffer.extend(chunk)
            if len(buffer) >= chunk_duration_frames:
                result = await self.transcribe(bytes(buffer), sample_rate)
                if not result.is_empty:
                    result.is_partial = True
                    yield result
                buffer.clear()

        if buffer:
            result = await self.transcribe(bytes(buffer), sample_rate)
            if not result.is_empty:
                yield result

    @property
    def is_ready(self) -> bool:
        """Whether the engine is initialized and ready."""
        return self._initialized

    @property
    def model_name(self) -> str:
        """Name of the loaded model."""
        return self._model_name

    @abstractmethod
    async def close(self) -> None:
        """Release all resources."""
        ...
