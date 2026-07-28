"""Text-to-Speech Engine.

Converts text responses to spoken audio using Piper TTS locally.
Generates WAV audio that can be streamed to the frontend.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

from backend.app.config import settings


class TextToSpeech:
    """Text-to-speech engine using Piper TTS."""

    def __init__(self) -> None:
        self._model = None
        self._voice = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the Piper TTS engine."""
        try:
            import piper
            from piper import PiperVoice

            # Look for voice model
            voice_name = settings.PIPER_VOICE_MODEL
            voice_path = settings.PIPER_VOICE_PATH

            if voice_path:
                model_path = Path(voice_path)
            else:
                # Search in data/models directory
                models_dir = settings.get_model_path()
                model_path = models_dir / f"{voice_name}.onnx"

                if not model_path.exists():
                    logger.warning(
                        f"Piper voice model not found at {model_path}. "
                        f"Please download from https://github.com/rhasspy/piper/releases"
                    )
                    return False

            logger.info(f"Loading Piper voice: {model_path.name}...")
            self._voice = PiperVoice.load(str(model_path))
            self._initialized = True
            logger.info("✓ Text-to-speech engine ready")
            return True

        except ImportError:
            logger.warning("piper-tts not installed. TTS will not be available.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}")
            return False

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._voice is not None

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes.

        Args:
            text: Text to speak.

        Returns:
            WAV audio bytes.
        """
        if not self.is_ready or not text.strip():
            return b""

        try:
            import piper

            # Generate audio
            audio_stream = io.BytesIO()
            with wave.open(audio_stream, "wb") as wav_file:
                self._voice.synthesize(
                    text,
                    wav_file,
                    speaker_id=None,  # Use default speaker
                    length_scale=1.0 / settings.TTS_SPEED,
                )

            audio_bytes = audio_stream.getvalue()
            logger.debug(f"Synthesized {len(text)} chars -> {len(audio_bytes)} bytes audio")
            return audio_bytes

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return b""

    async def synthesize_stream(
        self,
        text: str,
        chunk_size_ms: int = 200,
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text and stream audio chunks.

        Args:
            text: Text to speak.
            chunk_size_ms: Size of each audio chunk in milliseconds.

        Yields:
            Audio chunks as bytes.
        """
        audio_bytes = await self.synthesize(text)
        if not audio_bytes:
            return

        # Parse WAV header to get audio data
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                sample_rate = wav.getframerate()
                frame_width = wav.getsampwidth()
                frames = wav.readframes(wav.getnframes())

            # Calculate chunk size in bytes
            chunk_frames = int(sample_rate * chunk_size_ms / 1000)
            chunk_bytes = chunk_frames * frame_width

            # Stream in chunks
            for i in range(0, len(frames), chunk_bytes):
                chunk = frames[i:i + chunk_bytes]
                if chunk:
                    yield chunk

        except Exception as e:
            logger.error(f"Audio streaming failed: {e}")

    async def close(self) -> None:
        """Release resources."""
        self._voice = None
        self._initialized = False
        logger.info("TTS engine shut down")
