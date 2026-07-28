"""Faster-Whisper Speech-to-Text Implementation.

Uses the faster-whisper library for local, GPU-accelerated
speech recognition with high accuracy and speed.
Supports automatic language detection and VAD filtering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from backend.app.config import settings
from backend.app.speech_to_text.engine import STTEngine, STTResult


class FasterWhisperSTT(STTEngine):
    """Speech-to-text using Faster-Whisper (local, GPU-accelerated)."""

    def __init__(self) -> None:
        super().__init__()
        self._model = None
        self._device: str = "cpu"
        self._compute_type: str = "int8"

    async def initialize(self) -> bool:
        """Load the Faster-Whisper model."""
        try:
            from faster_whisper import WhisperModel

            # Auto-detect device
            device = settings.WHISPER_DEVICE
            compute_type = settings.WHISPER_COMPUTE_TYPE

            if device == "auto":
                try:
                    import torch
                    self._device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    self._device = "cpu"
            else:
                self._device = device

            if compute_type == "auto":
                self._compute_type = "float16" if self._device == "cuda" else "int8"
            else:
                self._compute_type = compute_type

            model_path = str(settings.get_model_path())
            model_size = settings.WHISPER_MODEL_SIZE

            logger.info(
                f"Loading Whisper model '{model_size}' "
                f"(device={self._device}, compute={self._compute_type})..."
            )

            self._model = WhisperModel(
                model_size_or_path=model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=model_path,
            )

            self._model_name = f"faster-whisper/{model_size}"
            self._initialized = True
            logger.info(f"✓ Faster-Whisper STT ready ({model_size}, {self._device})")
            return True

        except ImportError:
            logger.warning("faster-whisper not installed. STT unavailable.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Faster-Whisper: {e}")
            return False

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> STTResult:
        """Transcribe PCM audio bytes to text."""
        if not self.is_ready or not self._model:
            return STTResult(text="", error="STT engine not initialized")

        try:
            # Convert 16-bit PCM bytes to float32 array
            audio_array = (
                np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                / 32768.0
            )

            # Run transcription
            segments, info = self._model.transcribe(
                audio_array,
                beam_size=5,
                language=language,  # None = auto-detect
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    max_speech_duration_s=30,
                    min_silence_duration_ms=500,
                ),
            )

            # Collect segments
            segment_list = []
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
                segment_list.append({
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "end": segment.end,
                    "confidence": getattr(segment, "confidence", 0.0),
                })

            transcript = " ".join(text_parts)
            duration = info.duration if hasattr(info, "duration") else 0.0

            logger.debug(
                f"Transcribed {len(transcript)} chars "
                f"(lang={info.language if hasattr(info, 'language') else 'auto'}, "
                f"prob={info.language_probability if hasattr(info, 'language_probability') else 0:.2f})"
            )

            return STTResult(
                text=transcript,
                confidence=getattr(info, "average_logprob", 0.0),
                language=info.language if hasattr(info, "language") else "en",
                duration_seconds=duration,
                segments=segment_list,
            )

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return STTResult(text="", error=str(e))

    async def transcribe_file(
        self,
        file_path: str | Path,
        language: Optional[str] = None,
    ) -> STTResult:
        """Transcribe an audio file."""
        if not self.is_ready or not self._model:
            return STTResult(text="", error="STT engine not initialized")

        try:
            segments, info = self._model.transcribe(
                str(file_path),
                beam_size=5,
                language=language,
                vad_filter=True,
            )

            text_parts = []
            segment_list = []
            for segment in segments:
                text_parts.append(segment.text.strip())
                segment_list.append({
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "end": segment.end,
                })

            transcript = " ".join(text_parts)
            logger.info(f"File transcribed ({len(transcript)} chars)")

            return STTResult(
                text=transcript,
                language=info.language if hasattr(info, "language") else "en",
                duration_seconds=getattr(info, "duration", 0.0),
                segments=segment_list,
            )

        except Exception as e:
            logger.error(f"File transcription failed: {e}")
            return STTResult(text="", error=str(e))

    async def close(self) -> None:
        """Release model resources."""
        self._model = None
        self._initialized = False
        logger.info("Faster-Whisper STT shut down")
