"""Audio Processor.

Prepares audio data for speech recognition:
- Resampling to target sample rate
- Channel conversion (stereo to mono)
- Noise reduction (optional)
- Normalization
- Format conversion
"""

from __future__ import annotations

import io
import struct
import wave
from typing import Optional

import numpy as np
from loguru import logger


class AudioProcessor:
    """Processes audio data for optimal speech recognition."""

    TARGET_SAMPLE_RATE = 16000

    @staticmethod
    def convert_to_mono(audio_data: bytes, channels: int = 2) -> bytes:
        """Convert stereo audio to mono by averaging channels.

        Args:
            audio_data: Raw PCM audio bytes (16-bit).
            channels: Number of audio channels (1 or 2).

        Returns:
            Mono PCM audio bytes.
        """
        if channels == 1:
            return audio_data

        samples = np.frombuffer(audio_data, dtype=np.int16)
        # Reshape to (num_frames, channels) and average
        samples = samples.reshape(-1, channels)
        mono = np.mean(samples, axis=1, dtype=np.int16)
        return mono.tobytes()

    @staticmethod
    def resample(
        audio_data: bytes,
        original_rate: int,
        target_rate: int = 16000,
    ) -> bytes:
        """Resample audio to a target sample rate.

        Args:
            audio_data: Raw PCM audio bytes (16-bit, mono).
            original_rate: Original sample rate.
            target_rate: Desired sample rate.

        Returns:
            Resampled PCM audio bytes.
        """
        if original_rate == target_rate:
            return audio_data

        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

        # Simple linear interpolation resampling
        ratio = original_rate / target_rate
        new_length = int(len(samples) / ratio)

        indices = np.arange(new_length) * ratio
        indices_floor = np.floor(indices).astype(int)
        indices_ceil = np.minimum(indices_floor + 1, len(samples) - 1)
        frac = indices - indices_floor

        resampled = (
            samples[indices_floor] * (1 - frac) + samples[indices_ceil] * frac
        )

        return resampled.astype(np.int16).tobytes()

    @staticmethod
    def normalize(audio_data: bytes, target_level: float = 0.95) -> bytes:
        """Normalize audio amplitude to prevent clipping.

        Args:
            audio_data: Raw PCM audio bytes (16-bit).
            target_level: Target peak level (0.0 - 1.0).

        Returns:
            Normalized PCM audio bytes.
        """
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        peak = np.max(np.abs(samples))
        if peak > 0:
            scale = min(target_level * 32768.0 / peak, 2.0)
            samples = np.clip(samples * scale, -32768, 32767)
        return samples.astype(np.int16).tobytes()

    @staticmethod
    def reduce_noise(
        audio_data: bytes,
        noise_floor: float = 0.02,
    ) -> bytes:
        """Simple noise gate / spectral noise reduction.

        Args:
            audio_data: Raw PCM audio bytes (16-bit).
            noise_floor: Threshold below which to attenuate.

        Returns:
            Noise-reduced PCM audio bytes.
        """
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

        # Simple noise gate: zero out samples below threshold
        threshold = noise_floor * 32768.0
        mask = np.abs(samples) > threshold
        samples = samples * mask

        return samples.astype(np.int16).tobytes()

    @staticmethod
    def prepare_for_stt(
        audio_data: bytes,
        source_sample_rate: int = 16000,
        source_channels: int = 1,
        normalize_audio: bool = True,
        reduce_noise_flag: bool = False,
    ) -> bytes:
        """Prepare audio data for speech-to-text processing.

        Full pipeline: mono conversion → resampling → normalization → noise reduction.

        Args:
            audio_data: Raw PCM audio bytes.
            source_sample_rate: Original sample rate.
            source_channels: Original number of channels.
            normalize_audio: Whether to normalize amplitude.
            reduce_noise_flag: Whether to apply noise reduction.

        Returns:
            Processed PCM audio bytes (16-bit, 16kHz, mono).
        """
        data = audio_data

        # Step 1: Convert to mono
        if source_channels > 1:
            data = AudioProcessor.convert_to_mono(data, source_channels)

        # Step 2: Resample to target rate
        data = AudioProcessor.resample(data, source_sample_rate, 16000)

        # Step 3: Normalize
        if normalize_audio:
            data = AudioProcessor.normalize(data)

        # Step 4: Noise reduction
        if reduce_noise_flag:
            data = AudioProcessor.reduce_noise(data)

        return data

    @staticmethod
    def pcm_to_wav(
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        bit_depth: int = 16,
    ) -> bytes:
        """Wrap raw PCM data in a WAV container.

        Args:
            audio_data: Raw PCM audio bytes.
            sample_rate: Sample rate in Hz.
            channels: Number of channels.
            bit_depth: Bits per sample.

        Returns:
            Complete WAV file as bytes.
        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(bit_depth // 8)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_data)
        return buffer.getvalue()

    @staticmethod
    def wav_to_pcm(wav_data: bytes) -> tuple[bytes, int, int]:
        """Extract raw PCM data from a WAV file.

        Args:
            wav_data: Complete WAV file bytes.

        Returns:
            Tuple of (pcm_data, sample_rate, channels).
        """
        with wave.open(io.BytesIO(wav_data), "rb") as wav:
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            frames = wav.readframes(wav.getnframes())
        return frames, sample_rate, channels
