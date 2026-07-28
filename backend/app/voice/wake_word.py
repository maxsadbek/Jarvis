"""Wake Word Detector.

Listens for the JARVIS wake word to activate the assistant.
Uses a simple keyword spotting approach with VAD (Voice Activity Detection).
"""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Callable, Optional

import numpy as np
from loguru import logger

from backend.app.config import settings


class WakeWordDetector:
    """Detects wake word 'JARVIS' from microphone input."""

    def __init__(self) -> None:
        self._listening = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._vad = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the wake word detector.

        Uses WebRTC VAD for voice activity detection and
        a simple threshold-based detection for the wake word.
        """
        try:
            import webrtcvad

            self._vad = webrtcvad.Vad()
            # Set aggressiveness (0-3, 3 being most aggressive)
            self._vad.set_mode(2)

            self._initialized = True
            logger.info("✓ Wake word detector initialized")
            return True

        except ImportError:
            logger.warning("webrtcvad not installed. Wake word detection disabled.")
            return False

    @property
    def is_ready(self) -> bool:
        return self._initialized

    @property
    def is_active(self) -> bool:
        return settings.WAKE_WORD_ENABLED and self._listening

    def set_callback(self, callback: Callable) -> None:
        """Set callback to trigger when wake word is detected."""
        self._callback = callback

    async def start_listening(self) -> None:
        """Start listening for the wake word."""
        if self._listening or not self.is_ready:
            return

        self._listening = True
        logger.info(f"Listening for wake word '{settings.WAKE_WORD}'...")

        loop = asyncio.get_event_loop()

        def audio_callback(indata, frames, time_info, status):
            """Callback from sounddevice for incoming audio."""
            if status:
                logger.debug(f"Audio callback status: {status}")
            self._audio_queue.put(indata.copy())

        try:
            import sounddevice as sd

            self._stream = sd.InputStream(
                samplerate=settings.SAMPLE_RATE,
                channels=settings.CHANNELS,
                callback=audio_callback,
                blocksize=int(settings.SAMPLE_RATE * 0.03),  # 30ms frames
            )
            self._stream.start()

            # Run detection in a background thread
            self._thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
            )
            self._thread.start()

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self._listening = False

    def _detection_loop(self) -> None:
        """Background loop to detect wake word."""
        import webrtcvad

        # Buffer for voice activity detection
        audio_buffer = bytearray()
        vad_mode = 2

        while self._listening:
            try:
                data = self._audio_queue.get(timeout=1.0)
                audio_bytes = data.tobytes()

                # Check voice activity
                is_speech = self._vad.is_speech(audio_bytes, settings.SAMPLE_RATE)

                if is_speech:
                    audio_buffer.extend(audio_bytes)

                    # Process when we have ~1 second of audio
                    if len(audio_buffer) >= settings.SAMPLE_RATE * 2:  # 2 seconds
                        # Convert to text for wake word detection
                        self._check_wake_word(bytes(audio_buffer))
                        audio_buffer.clear()
                else:
                    # Keep a short buffer for continuous speech
                    if len(audio_buffer) > settings.SAMPLE_RATE * 3:
                        audio_buffer = audio_buffer[-settings.SAMPLE_RATE:]

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Wake word detection error: {e}")

    def _check_wake_word(self, audio_bytes: bytes) -> None:
        """Check if audio contains the wake word using simple energy detection.

        Note: For true wake word detection, this should use a proper
        keyword spotting model (e.g., Porcupine, Snowboy, or a fine-tuned model).
        This implementation uses a simplified approach.
        """
        try:
            # Convert to float array and calculate energy
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            energy = np.sqrt(np.mean(audio_array ** 2))

            # Simple energy threshold detection
            # In production, replace with actual wake word model
            threshold = settings.WAKE_WORD_SENSITIVITY * 500
            if energy > threshold:
                logger.info("Wake word detected (energy-based)")
                if self._callback:
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._callback())
                        loop.close()
                    except Exception as e:
                        logger.error(f"Wake word callback failed: {e}")

        except Exception as e:
            logger.error(f"Wake word check error: {e}")

    def stop_listening(self) -> None:
        """Stop listening for wake word."""
        self._listening = False
        if hasattr(self, "_stream"):
            self._stream.stop()
            self._stream.close()

    async def close(self) -> None:
        """Clean up resources."""
        self.stop_listening()
        self._vad = None
        logger.info("Wake word detector shut down")
