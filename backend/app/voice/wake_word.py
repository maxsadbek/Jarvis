"""Wake Word Detector.

Detects the JARVIS wake word from microphone input.
Supports multiple detection engines:
1. Porcupine (Picovoice) - High accuracy, cross-platform
2. Energy-based (fallback) - Simple loudness detection
"""

from __future__ import annotations

import asyncio
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from loguru import logger

from backend.app.config import settings


class WakeWordDetector:
    """Detects the JARVIS wake word from microphone input."""

    def __init__(self) -> None:
        self._listening = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._porcupine = None
        self._vad = None
        self._initialized = False
        self._engine_name: str = "none"

    async def initialize(self) -> bool:
        """Initialize the wake word detector.

        Tries Porcupine first, falls back to energy-based detection.
        """
        # Try Porcupine first
        if await self._init_porcupine():
            self._engine_name = "porcupine"
            self._initialized = True
            logger.info(f"✓ Wake word detector initialized (Porcupine)")
            return True

        # Fall back to WebRTC VAD + energy-based
        if await self._init_vad_energy():
            self._engine_name = "energy"
            self._initialized = True
            logger.info(f"✓ Wake word detector initialized (energy-based)")
            return True

        logger.warning("Wake word detection not available")
        return False

    async def _init_porcupine(self) -> bool:
        """Initialize Porcupine wake word engine."""
        try:
            import pvporcupine

            keywords = [settings.WAKE_WORD.lower()]
            access_key = settings.PORCUPINE_API_KEY

            if access_key:
                self._porcupine = pvporcupine.create(
                    access_key=access_key,
                    keywords=keywords,
                    sensitivities=[settings.WAKE_WORD_SENSITIVITY],
                )
                logger.info("Porcupine wake word engine initialized (API key)")
                return True
            else:
                # Try with built-in keyword files
                keyword_path = Path("data/models") / f"{settings.WAKE_WORD}_en_windows_v3_0_0.ppn"
                if keyword_path.exists():
                    self._porcupine = pvporcupine.create(
                        keyword_paths=[str(keyword_path)],
                        sensitivities=[settings.WAKE_WORD_SENSITIVITY],
                    )
                    logger.info("Porcupine wake word engine initialized (keyword file)")
                    return True
                logger.warning(
                    f"Porcupine not configured. Provide PORCUPINE_API_KEY or place "
                    f"keyword file at {keyword_path}"
                )
                return False

        except ImportError:
            logger.debug("pvporcupine not installed, falling back to energy detection")
            return False
        except Exception as e:
            logger.warning(f"Porcupine init failed: {e}")
            return False

    async def _init_vad_energy(self) -> bool:
        """Initialize WebRTC VAD for energy-based detection."""
        try:
            import webrtcvad

            self._vad = webrtcvad.Vad()
            self._vad.set_mode(2)
            return True
        except ImportError:
            return False

    @property
    def is_ready(self) -> bool:
        return self._initialized

    @property
    def is_active(self) -> bool:
        return settings.WAKE_WORD_ENABLED and self._listening

    @property
    def engine_name(self) -> str:
        return self._engine_name

    def set_callback(self, callback: Callable) -> None:
        """Set callback to trigger when wake word is detected.

        The callback will be called in a background thread.
        """
        self._callback = callback

    async def start_listening(self) -> None:
        """Start listening for the wake word."""
        if self._listening or not self.is_ready:
            return

        self._listening = True
        logger.info(f"Listening for wake word '{settings.WAKE_WORD}'...")

        try:
            import sounddevice as sd

            def audio_callback(indata, frames, time_info, status):
                """Callback from sounddevice for incoming audio."""
                if status:
                    logger.debug(f"Audio callback status: {status}")
                self._audio_queue.put(indata.copy())

            self._stream = sd.InputStream(
                samplerate=settings.SAMPLE_RATE,
                channels=1,
                callback=audio_callback,
                blocksize=int(settings.SAMPLE_RATE * 0.03),  # 30ms frames
            )
            self._stream.start()

            # Run detection in a background thread
            self._thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
                name="wake-word-detector",
            )
            self._thread.start()

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self._listening = False

    def _detection_loop(self) -> None:
        """Background loop to detect wake word."""
        audio_buffer = np.array([], dtype=np.int16)
        porcupine_frame_size = self._porcupine.frame_length if self._porcupine else 512
        vad_frame_ms = 30
        vad_frame_samples = int(settings.SAMPLE_RATE * vad_frame_ms / 1000)

        while self._listening:
            try:
                data = self._audio_queue.get(timeout=0.5)
                audio_buffer = np.append(audio_buffer, data.flatten())

                if self._porcupine:
                    # Porcupine detection
                    while len(audio_buffer) >= porcupine_frame_size:
                        frame = audio_buffer[:porcupine_frame_size]
                        audio_buffer = audio_buffer[porcupine_frame_size:]

                        result = self._porcupine.process(frame)
                        if result >= 0:
                            logger.info(f"Wake word '{settings.WAKE_WORD}' detected!")
                            self._on_wake_word_detected()

                elif self._vad:
                    # Energy-based detection with VAD
                    # Process in VAD-sized frames
                    while len(audio_buffer) >= vad_frame_samples:
                        frame = audio_buffer[:vad_frame_samples]
                        audio_buffer = audio_buffer[vad_frame_samples:]

                        frame_bytes = frame.astype(np.int16).tobytes()
                        try:
                            is_speech = self._vad.is_speech(frame_bytes, settings.SAMPLE_RATE)
                        except Exception:
                            is_speech = False

                        if is_speech:
                            # Energy check for wake word
                            energy = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
                            threshold = settings.WAKE_WORD_SENSITIVITY * 500

                            if energy > threshold:
                                logger.info("Wake word detected (energy-based)")
                                self._on_wake_word_detected()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Wake word detection error: {e}")

    def _on_wake_word_detected(self) -> None:
        """Handle wake word detection."""
        if self._callback:
            try:
                if asyncio.iscoroutinefunction(self._callback):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._callback())
                    loop.close()
                else:
                    self._callback()
            except Exception as e:
                logger.error(f"Wake word callback failed: {e}")

    def stop_listening(self) -> None:
        """Stop listening for wake word."""
        self._listening = False
        if hasattr(self, "_stream") and self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    async def close(self) -> None:
        """Clean up resources."""
        self.stop_listening()
        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None
        self._vad = None
        logger.info("Wake word detector shut down")
