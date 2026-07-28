"""Speech-to-Text Engine.

Converts audio from microphone to text using Faster-Whisper.
Supports both file-based and streaming transcription.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

from backend.app.config import settings


class SpeechToText:
    """Speech-to-text engine using Faster-Whisper."""

    def __init__(self) -> None:
        self._model = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Load the Whisper model."""
        try:
            from faster_whisper import WhisperModel

            device = settings.WHISPER_DEVICE
            compute_type = settings.WHISPER_COMPUTE_TYPE

            # Auto-detect device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"

            # Auto-detect compute type
            if compute_type == "auto":
                compute_type = "float16" if device == "cuda" else "int8"

            model_path = str(settings.get_model_path())

            logger.info(
                f"Loading Whisper model '{settings.WHISPER_MODEL_SIZE}' "
                f"(device={device}, compute={compute_type})..."
            )

            self._model = WhisperModel(
                model_size_or_path=settings.WHISPER_MODEL_SIZE,
                device=device,
                compute_type=compute_type,
                download_root=model_path,
            )

            self._initialized = True
            logger.info("✓ Speech-to-text engine ready")
            return True

        except ImportError:
            logger.warning("faster-whisper not installed. STT will not be available.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize STT engine: {e}")
            return False

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._model is not None

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio bytes to text.

        Args:
            audio_data: Raw PCM audio bytes (16-bit, mono).
            sample_rate: Sample rate of the audio (default: 16000).

        Returns:
            Transcribed text.
        """
        if not self.is_ready:
            logger.warning("STT not ready")
            return ""

        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            segments, info = self._model.transcribe(
                audio_array,
                beam_size=5,
                language=None,  # Auto-detect
                vad_filter=True,  # Filter out silence
            )

            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            transcript = " ".join(text_parts)
            logger.debug(f"Transcribed: {transcript[:100]}...")
            return transcript

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    async def transcribe_file(self, file_path: str | Path) -> str:
        """Transcribe an audio file.

        Args:
            file_path: Path to the audio file.

        Returns:
            Transcribed text.
        """
        if not self.is_ready:
            return ""

        try:
            segments, info = self._model.transcribe(
                str(file_path),
                beam_size=5,
                vad_filter=True,
            )

            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            transcript = " ".join(text_parts)
            logger.info(f"File transcribed ({len(transcript)} chars)")
            return transcript

        except Exception as e:
            logger.error(f"File transcription failed: {e}")
            return ""

    async def transcribe_stream(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        sample_rate: int = 16000,
    ) -> AsyncGenerator[str, None]:
        """Transcribe streaming audio.

        Args:
            audio_generator: Async generator yielding audio chunks.
            sample_rate: Audio sample rate.

        Yields:
            Partial transcripts as they become available.
        """
        buffer = bytearray()

        async for chunk in audio_generator:
            buffer.extend(chunk)

            # Process in ~2 second chunks
            if len(buffer) >= sample_rate * 4:  # 4 seconds of audio
                text = await self.transcribe(bytes(buffer), sample_rate)
                if text.strip():
                    yield text
                buffer.clear()

        # Process remaining audio
        if buffer:
            text = await self.transcribe(bytes(buffer), sample_rate)
            if text.strip():
                yield text

    async def close(self) -> None:
        """Release resources."""
        self._model = None
        self._initialized = False
        logger.info("STT engine shut down")
