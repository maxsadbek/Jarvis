"""Audio Utilities.

Provides microphone recording, audio playback, and device management
for the JARVIS voice assistant.
"""

from __future__ import annotations

import asyncio
import io
import struct
import wave
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Optional

import numpy as np
from loguru import logger

from backend.app.config import settings


@dataclass
class AudioDevice:
    """Information about an audio input/output device."""

    id: int
    name: str
    channels: int
    sample_rate: int
    is_input: bool
    is_default: bool


class MicrophoneStream:
    """Async microphone audio stream for real-time capture."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration_ms: int = 100,
        device_id: Optional[int] = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self._device_id = device_id
        self._stream = None
        self._is_running = False
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def start(self) -> bool:
        """Start the microphone stream.

        Returns:
            True if started successfully.
        """
        try:
            import sounddevice as sd

            def callback(indata, frames, time_info, status):
                """Sounddevice callback (called from audio thread)."""
                if status:
                    logger.debug(f"Audio status: {status}")
                # Queue the audio data for async processing
                audio_bytes = indata.tobytes()
                if self._audio_queue:
                    try:
                        # Use put_nowait since we're in a callback thread
                        loop = asyncio.get_event_loop()
                        future = asyncio.run_coroutine_threadsafe(
                            self._audio_queue.put(audio_bytes), loop
                        )
                        future.result(timeout=0.1)
                    except Exception:
                        pass

            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                callback=callback,
                blocksize=self._chunk_size,
                device=self._device_id,
                dtype="int16",
            )
            self._stream.start()
            self._is_running = True
            logger.info(
                f"Microphone stream started "
                f"(rate={self._sample_rate}, channels={self._channels})"
            )
            return True

        except ImportError:
            logger.warning("sounddevice not installed. Microphone unavailable.")
            return False
        except Exception as e:
            logger.error(f"Failed to start microphone: {e}")
            return False

    async def read_chunk(self) -> Optional[bytes]:
        """Read a single audio chunk from the microphone.

        Returns:
            Audio chunk bytes, or None if stream ended.
        """
        try:
            chunk = await asyncio.wait_for(
                self._audio_queue.get(), timeout=1.0
            )
            return chunk
        except asyncio.TimeoutError:
            return None

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Async generator yielding audio chunks continuously."""
        while self._is_running:
            chunk = await self.read_chunk()
            if chunk:
                yield chunk

    def stop(self) -> None:
        """Stop the microphone stream."""
        self._is_running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        logger.info("Microphone stream stopped")

    @property
    def is_active(self) -> bool:
        return self._is_running and self._stream is not None


class AudioPlayer:
    """Plays audio data through the system speakers."""

    def __init__(self) -> None:
        self._stream = None
        self._is_playing = False

    async def play(self, audio_data: bytes) -> None:
        """Play audio data.

        Args:
            audio_data: WAV format audio bytes.
        """
        try:
            import sounddevice as sd

            # Parse WAV to get parameters
            with wave.open(io.BytesIO(audio_data), "rb") as wav:
                sample_rate = wav.getframerate()
                channels = wav.getnchannels()
                frames = wav.readframes(wav.getnframes())

            # Convert to numpy array
            audio_array = np.frombuffer(frames, dtype=np.int16)

            self._is_playing = True

            # Play in a separate thread to avoid blocking
            def play_audio():
                sd.play(audio_array, samplerate=sample_rate)
                sd.wait()
                self._is_playing = False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, play_audio)

        except ImportError:
            logger.warning("sounddevice not installed. Playback unavailable.")
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
            self._is_playing = False

    async def play_stream(
        self,
        audio_chunks: AsyncGenerator[bytes, None],
    ) -> None:
        """Play streaming audio chunks.

        Args:
            audio_chunks: Async generator yielding audio chunks.
        """
        try:
            import sounddevice as sd

            self._is_playing = True
            buffer = bytearray()

            async for chunk in audio_chunks:
                buffer.extend(chunk)

            if buffer:
                audio_array = np.frombuffer(buffer, dtype=np.int16)
                sd.play(audio_array, samplerate=settings.PIPER_OUTPUT_SAMPLE_RATE)
                sd.wait()

        except ImportError:
            logger.warning("sounddevice not installed. Playback unavailable.")
        except Exception as e:
            logger.error(f"Streaming playback failed: {e}")
        finally:
            self._is_playing = False

    def stop(self) -> None:
        """Stop current playback."""
        try:
            import sounddevice as sd
            sd.stop()
        except ImportError:
            pass
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        return self._is_playing


def list_audio_devices() -> list[AudioDevice]:
    """List all available audio input/output devices.

    Returns:
        List of AudioDevice descriptors.
    """
    try:
        import sounddevice as sd

        devices = []
        for i, dev in enumerate(sd.query_devices()):
            devices.append(AudioDevice(
                id=i,
                name=dev["name"],
                channels=dev["max_input_channels"],
                sample_rate=int(dev["default_samplerate"]),
                is_input=dev["max_input_channels"] > 0,
                is_default=i == sd.default.device[0],
            ))
        return devices
    except ImportError:
        logger.warning("sounddevice not installed")
        return []
    except Exception as e:
        logger.error(f"Failed to list audio devices: {e}")
        return []


def get_default_input_device() -> Optional[AudioDevice]:
    """Get the default microphone device.

    Returns:
        Default input AudioDevice or None.
    """
    devices = list_audio_devices()
    input_devices = [d for d in devices if d.is_input]
    if input_devices:
        default = next((d for d in input_devices if d.is_default), input_devices[0])
        return default
    return None


def record_audio(
    duration_seconds: float = 5.0,
    sample_rate: int = 16000,
) -> Optional[bytes]:
    """Record audio from the default microphone.

    Args:
        duration_seconds: Recording duration.
        sample_rate: Sample rate.

    Returns:
        WAV format audio bytes, or None on failure.
    """
    try:
        import sounddevice as sd

        logger.info(f"Recording for {duration_seconds}s...")
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        # Wrap in WAV
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(recording.tobytes())

        logger.info(f"Recorded {len(recording)} samples")
        return buffer.getvalue()

    except ImportError:
        logger.warning("sounddevice not installed")
        return None
    except Exception as e:
        logger.error(f"Recording failed: {e}")
        return None
