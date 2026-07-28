"""Audio Streamer.

Manages streaming of synthesized audio to WebSocket clients.
Handles chunking, rate limiting, and audio format conversion.
"""

from __future__ import annotations

import asyncio
import io
import wave
from typing import AsyncGenerator, Optional

from loguru import logger


class AudioStreamer:
    """Streams audio data in chunks for real-time playback.

    Handles the low-level details of slicing audio data into
    appropriately-sized chunks for smooth client playback.
    """

    def __init__(self, chunk_size_ms: int = 200) -> None:
        self._chunk_size_ms = chunk_size_ms
        self._is_streaming = False

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    async def stream_wav(
        self,
        wav_data: bytes,
        chunk_size_ms: Optional[int] = None,
    ) -> AsyncGenerator[tuple[bytes, int, int], None]:
        """Stream WAV audio data in chunks.

        Parses the WAV header, then yields audio data chunks
        with their sample rate and format info.

        Args:
            wav_data: Complete WAV file bytes.
            chunk_size_ms: Chunk size in ms (overrides default).

        Yields:
            Tuples of (audio_chunk_bytes, sample_rate, chunk_index).
        """
        if len(wav_data) < 44:
            logger.warning("WAV data too short (no header)")
            return

        chunk_ms = chunk_size_ms or self._chunk_size_ms
        self._is_streaming = True

        try:
            # Parse WAV header
            with wave.open(io.BytesIO(wav_data), "rb") as wav:
                sample_rate = wav.getframerate()
                sample_width = wav.getsampwidth()
                channels = wav.getnchannels()
                total_frames = wav.getnframes()
                raw_data = wav.readframes(total_frames)

            # Calculate chunk size
            bytes_per_frame = sample_width * channels
            frames_per_chunk = int(sample_rate * chunk_ms / 1000)
            chunk_bytes = frames_per_chunk * bytes_per_frame

            chunk_index = 0
            for i in range(0, len(raw_data), chunk_bytes):
                chunk = raw_data[i:i + chunk_bytes]
                if len(chunk) > 0:
                    yield (chunk, sample_rate, chunk_index)
                    chunk_index += 1
                    # Small yield to let event loop breathe
                    await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Audio streaming failed: {e}")
        finally:
            self._is_streaming = False

    @staticmethod
    def calculate_duration(audio_data: bytes, sample_rate: int, bytes_per_sample: int = 2, channels: int = 1) -> float:
        """Calculate audio duration in seconds.

        Args:
            audio_data: Raw PCM audio data (no header).
            sample_rate: Sample rate in Hz.
            bytes_per_sample: Bytes per sample (default 2 for 16-bit).
            channels: Number of channels.

        Returns:
            Duration in seconds.
        """
        total_samples = len(audio_data) / (bytes_per_sample * channels)
        return total_samples / sample_rate

    async def close(self) -> None:
        """Stop streaming and clean up."""
        self._is_streaming = False
