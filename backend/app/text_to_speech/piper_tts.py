"""Piper TTS Implementation.

Local text-to-speech using Piper TTS engine.
Produces high-quality WAV audio with multiple voice options.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.app.config import settings
from backend.app.text_to_speech.engine import TTSEngine, TTSResult


class PiperTTS(TTSEngine):
    """Text-to-speech using Piper TTS (local, fast)."""

    def __init__(self) -> None:
        super().__init__()
        self._voice = None

    async def initialize(self) -> bool:
        """Load the Piper voice model."""
        try:
            from piper import PiperVoice

            voice_name = settings.PIPER_VOICE_MODEL
            voice_path = settings.PIPER_VOICE_PATH
            models_dir = settings.get_model_path()

            if voice_path:
                model_path = Path(voice_path)
            else:
                # Try the configured voice first, then the fallback list, so
                # an Uzbek-friendly voice (ru_RU / tr_TR) is used when the
                # primary model file is missing.
                model_path = None
                candidates = [voice_name, *settings.PIPER_VOICE_FALLBACK_MODELS]
                for candidate in candidates:
                    candidate_path = models_dir / f"{candidate}.onnx"
                    if candidate_path.exists():
                        model_path = candidate_path
                        voice_name = candidate
                        break

                if model_path is None:
                    logger.warning(
                        f"Piper voice model not found for any of: "
                        f"{', '.join(candidates)}.\n"
                        f"Download from: https://github.com/rhasspy/piper/releases\n"
                        f"Place the .onnx and .json files in {models_dir}"
                    )
                    return False

            json_path = model_path.with_suffix(".json")
            if not json_path.exists():
                logger.warning(
                    f"Piper voice config not found at {json_path}. "
                    f"The .json file must accompany the .onnx model."
                )
                return False

            logger.info(f"Loading Piper voice: {model_path.name}...")
            self._voice = PiperVoice.load(str(model_path))
            self._voice_name = voice_name
            self._initialized = True
            logger.info(f"✓ Piper TTS ready ({voice_name})")
            return True

        except ImportError:
            logger.warning("piper-tts not installed. TTS unavailable.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Piper TTS: {e}")
            return False

    async def synthesize(self, text: str) -> TTSResult:
        """Synthesize text to WAV audio."""
        if not self.is_ready or not self._voice or not text.strip():
            return TTSResult(
                audio_bytes=b"",
                text=text,
                error="TTS engine not initialized" if not self.is_ready else "Empty text",
            )

        try:
            audio_buffer = io.BytesIO()
            with wave.open(audio_buffer, "wb") as wav_file:
                self._voice.synthesize(
                    text,
                    wav_file,
                    speaker_id=None,
                    length_scale=1.0 / settings.TTS_SPEED,
                )

            audio_bytes = audio_buffer.getvalue()

            # Calculate duration from WAV header
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
                sample_rate = wav.getframerate()
                frames = wav.getnframes()
                duration = frames / sample_rate

            logger.debug(f"Synthesized {len(text)} chars -> {len(audio_bytes)} bytes ({duration:.1f}s)")

            return TTSResult(
                audio_bytes=audio_bytes,
                sample_rate=sample_rate,
                channels=1,
                bit_depth=16,
                format="wav",
                duration_seconds=duration,
                text=text,
            )

        except Exception as e:
            logger.error(f"Piper synthesis failed: {e}")
            return TTSResult(
                audio_bytes=b"",
                text=text,
                error=str(e),
            )

    async def close(self) -> None:
        """Release voice resources."""
        self._voice = None
        self._initialized = False
        logger.info("Piper TTS shut down")
