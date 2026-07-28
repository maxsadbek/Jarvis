"""Voice Activity Detection (VAD).

Detects when a person is speaking in an audio stream.
Uses WebRTC VAD for real-time speech/non-speech classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from loguru import logger


@dataclass
class VadConfig:
    """Configuration for Voice Activity Detection."""

    mode: int = 2  # WebRTC VAD aggressiveness (0-3, 3=most aggressive)
    sample_rate: int = 16000
    frame_duration_ms: int = 30  # Frame size in ms (10, 20, or 30)
    padding_duration_ms: int = 300  # Silence padding before/after speech
    threshold: float = 0.5
    min_speech_duration_ms: int = 200  # Minimum speech to consider valid
    min_silence_duration_ms: int = 500  # Silence to mark end of speech
    speech_buffer_seconds: float = 3.0  # Max speech buffer before processing


class VoiceActivityDetector:
    """Detects speech segments in audio using WebRTC VAD."""

    def __init__(self, config: Optional[VadConfig] = None) -> None:
        self._config = config or VadConfig()
        self._vad = None
        self._initialized = False

        # Audio buffer state
        self._speech_buffer = bytearray()
        self._is_speech_active = False
        self._silence_counter = 0
        self._speech_start_frame = 0
        self._total_frames = 0

    async def initialize(self) -> bool:
        """Initialize the WebRTC VAD engine."""
        try:
            import webrtcvad

            self._vad = webrtcvad.Vad()
            self._vad.set_mode(self._config.mode)
            self._initialized = True
            logger.debug(
                f"VAD initialized (mode={self._config.mode}, "
                f"frame={self._config.frame_duration_ms}ms)"
            )
            return True

        except ImportError:
            logger.warning("webrtcvad not installed. VAD disabled.")
            return False
        except Exception as e:
            logger.error(f"VAD initialization failed: {e}")
            return False

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._vad is not None

    def is_speech(self, audio_frame: bytes) -> bool:
        """Check if a single audio frame contains speech.

        Args:
            audio_frame: 16-bit PCM audio frame (must be 10, 20, or 30ms).

        Returns:
            True if the frame contains speech.
        """
        if not self.is_ready:
            return False

        try:
            return self._vad.is_speech(audio_frame, self._config.sample_rate)
        except Exception:
            return False

    def process_chunk(self, audio_chunk: bytes) -> Optional[bytes]:
        """Process an audio chunk and return speech segment if speech ends.

        Implements a simple state machine:
        - Accumulates audio while speech is detected
        - Returns accumulated speech when silence threshold is reached
        - Returns None if no speech end detected

        Args:
            audio_chunk: 16-bit PCM audio data.

        Returns:
            Speech segment bytes if speech segment completed, else None.
        """
        if not self.is_ready or not audio_chunk:
            return None

        frame_size = int(
            self._config.sample_rate
            * self._config.frame_duration_ms
            / 1000
            * 2  # 16-bit = 2 bytes
        )

        self._total_frames += 1
        has_speech = False

        # Process in VAD frame-sized chunks
        for i in range(0, len(audio_chunk), frame_size):
            frame = audio_chunk[i:i + frame_size]
            if len(frame) != frame_size:
                continue

            try:
                is_speech_frame = self._vad.is_speech(
                    frame, self._config.sample_rate
                )
            except Exception:
                continue

            if is_speech_frame:
                if not self._is_speech_active:
                    # Speech just started
                    self._is_speech_active = True
                    self._speech_start_frame = self._total_frames
                    self._speech_buffer.clear()
                self._silence_counter = 0
            elif self._is_speech_active:
                self._silence_counter += 1

            if self._is_speech_active:
                self._speech_buffer.extend(frame)

        # Check if speech segment ended
        silence_frame_count = int(
            self._config.min_silence_duration_ms
            / self._config.frame_duration_ms
        )

        if self._is_speech_active and self._silence_counter >= silence_frame_count:
            speech_duration_ms = (
                (self._total_frames - self._speech_start_frame)
                * self._config.frame_duration_ms
            )

            if speech_duration_ms >= self._config.min_speech_duration_ms:
                result = bytes(self._speech_buffer)
                self._reset()
                return result
            else:
                # Too short, discard
                self._reset()

        # Prevent buffer from growing too large
        max_buffer_size = int(
            self._config.sample_rate
            * self._config.speech_buffer_seconds
            * 2
        )
        if len(self._speech_buffer) > max_buffer_size:
            self._reset()

        return None

    def _reset(self) -> None:
        """Reset the speech detection state."""
        self._speech_buffer.clear()
        self._is_speech_active = False
        self._silence_counter = 0

    def flush(self) -> Optional[bytes]:
        """Flush any remaining speech in the buffer.

        Returns:
            Remaining speech bytes if any, else None.
        """
        if self._is_speech_active and len(self._speech_buffer) > 0:
            result = bytes(self._speech_buffer)
            self._reset()
            return result
        self._reset()
        return None

    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently being detected."""
        return self._is_speech_active

    @property
    def buffer_duration_ms(self) -> float:
        """Duration of audio in the current buffer in ms."""
        frames = len(self._speech_buffer) // 2  # 16-bit = 2 bytes/sample
        return (frames / self._config.sample_rate) * 1000

    async def close(self) -> None:
        """Release VAD resources."""
        self._vad = None
        self._initialized = False
        self._reset()
        logger.debug("VAD shut down")
