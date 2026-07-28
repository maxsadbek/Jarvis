"""Voice Pipeline.

The core voice processing pipeline that orchestrates:
1. Audio input -> Voice Activity Detection
2. Speech segments -> Speech-to-Text
3. Text -> AI Engine
4. AI Response -> Text-to-Speech
5. Audio output -> WebSocket client

Uses an event-driven architecture for real-time processing.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger

from backend.app.assistant_core.config import VoiceAssistantConfig
from backend.app.assistant_core.session import (
    SessionManager,
    SessionState,
    Utterance,
    VoiceSession,
)
from backend.app.core.engine import AIEngine
from backend.app.speech_to_text import (
    AudioProcessor,
    FasterWhisperSTT,
    STTEngine,
    STTResult,
    VadConfig,
    VoiceActivityDetector,
)
from backend.app.text_to_speech import (
    AudioStreamer,
    PiperTTS,
    TTSEngine,
)
from backend.app.models.schemas import ConnectionState


class PipelineEvent(str, Enum):
    """Events emitted by the voice pipeline."""

    LISTENING_STARTED = "listening_started"
    LISTENING_STOPPED = "listening_stopped"
    SPEECH_DETECTED = "speech_detected"
    SPEECH_ENDED = "speech_ended"
    TRANSCRIPTION_STARTED = "transcription_started"
    PARTIAL_TRANSCRIPT = "partial_transcript"
    TRANSCRIPTION_COMPLETE = "transcription_complete"
    AI_PROCESSING_STARTED = "ai_processing_started"
    AI_RESPONSE_READY = "ai_response_ready"
    TTS_STARTED = "tts_started"
    TTS_CHUNK = "tts_chunk"
    TTS_COMPLETE = "tts_complete"
    TURN_COMPLETE = "turn_complete"
    ERROR = "error"
    STATE_CHANGED = "state_changed"


@dataclass
class PipelineConfig:
    """Configuration for the voice pipeline."""

    voice: VoiceAssistantConfig = field(default_factory=VoiceAssistantConfig)
    audio_chunk_size: int = 3200  # 100ms at 16kHz 16-bit mono
    enable_vad: bool = True
    enable_partial_results: bool = True
    interrupt_on_new_speech: bool = True


class VoicePipeline:
    """Orchestrates the complete voice processing pipeline.

    The pipeline manages an async flow:
    Audio Input -> VAD -> STT -> AI Engine -> TTS -> Audio Output
    """

    def __init__(
        self,
        ai_engine: AIEngine,
        config: Optional[PipelineConfig] = None,
    ) -> None:
        self._ai_engine = ai_engine
        self._config = config or PipelineConfig()

        # Pipeline components (lazy initialized)
        self._stt: Optional[STTEngine] = None
        self._tts: Optional[TTSEngine] = None
        self._vad: Optional[VoiceActivityDetector] = None
        self._streamer: Optional[AudioStreamer] = None
        self._session_manager = SessionManager()

        # Pipeline state
        self._active_session: Optional[VoiceSession] = None
        self._is_running = False
        self._is_processing = False
        self._current_utterance: Optional[Utterance] = None

        # Event callbacks
        self._event_handlers: dict[PipelineEvent, list[Callable]] = {
            event: [] for event in PipelineEvent
        }

        # State callback (for WebSocket state updates)
        self._state_callback: Optional[Callable[[ConnectionState], Any]] = None

    # --- Initialization ---

    async def initialize(self) -> bool:
        """Initialize all pipeline components."""
        logger.info("Initializing voice pipeline...")

        try:
            # Initialize STT
            self._stt = FasterWhisperSTT()
            stt_ok = await self._stt.initialize()
            if stt_ok:
                logger.info(f"  STT: {self._stt.model_name}")
            else:
                logger.warning("  STT not available")

            # Initialize TTS
            self._tts = PiperTTS()
            tts_ok = await self._tts.initialize()
            if tts_ok:
                logger.info(f"  TTS: {self._tts.voice_name}")
            else:
                logger.warning("  TTS not available")

            # Initialize VAD
            vad_config = VadConfig(
                mode=self._config.voice.vad_mode,
                sample_rate=self._config.voice.input_sample_rate,
                frame_duration_ms=self._config.voice.vad_frame_duration_ms,
                min_speech_duration_ms=self._config.voice.vad_min_speech_duration_ms,
                min_silence_duration_ms=self._config.voice.vad_min_silence_duration_ms,
                speech_buffer_seconds=self._config.voice.vad_speech_buffer_seconds,
            )
            self._vad = VoiceActivityDetector(vad_config)
            vad_ok = await self._vad.initialize()
            if vad_ok:
                logger.info("  VAD ready")
            else:
                logger.info("  VAD not available (speech detection disabled)")

            # Initialize audio streamer
            self._streamer = AudioStreamer(
                chunk_size_ms=self._config.voice.tts_chunk_size_ms,
            )

            logger.info("Voice pipeline initialized")
            return True

        except Exception as e:
            logger.error(f"Voice pipeline initialization failed: {e}")
            return False

    @property
    def is_ready(self) -> bool:
        return self._stt is not None and self._stt.is_ready

    # --- Event System ---

    def on(self, event: PipelineEvent, handler: Callable) -> None:
        """Register an event handler."""
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: PipelineEvent, handler: Callable) -> None:
        """Remove an event handler."""
        if event in self._event_handlers:
            self._event_handlers[event] = [
                h for h in self._event_handlers[event] if h != handler
            ]

    async def _emit(self, event: PipelineEvent, data: Any = None) -> None:
        """Emit an event to all registered handlers."""
        for handler in self._event_handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler failed for {event}: {e}")

    def set_state_callback(self, callback: Callable[[ConnectionState], Any]) -> None:
        """Set a callback for state changes."""
        self._state_callback = callback

    async def _update_state(self, state: ConnectionState) -> None:
        """Update the pipeline state and notify callback."""
        if self._state_callback:
            try:
                await self._state_callback(state)
            except Exception as e:
                logger.warning(f"State callback failed: {e}")

    # --- Audio Processing ---

    async def process_audio_chunk(
        self,
        audio_chunk: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> Optional[str]:
        """Process an incoming audio chunk through the pipeline.

        This is the main entry point for streaming audio.
        Handles VAD -> STT -> AI -> (TTS handled separately).

        Args:
            audio_chunk: Raw PCM audio data.
            sample_rate: Sample rate of the audio.
            channels: Number of channels.

        Returns:
            Transcript text if speech segment completed, None otherwise.
        """
        if self._is_processing:
            return None

        if not self._active_session:
            return None

        # Preprocess audio
        processed = AudioProcessor.prepare_for_stt(
            audio_chunk,
            source_sample_rate=sample_rate,
            source_channels=channels,
        )

        # VAD segmentation
        if self._vad and self._config.enable_vad and self._vad.is_ready:
            speech_segment = self._vad.process_chunk(processed)
            if speech_segment is None:
                return None
        else:
            speech_segment = processed

        # Speech segment detected (capture duration before VAD resets its state)
        speech_duration_ms = self._vad.buffer_duration_ms if self._vad else 0
        await self._emit(PipelineEvent.SPEECH_ENDED, {
            "duration_ms": speech_duration_ms,
        })

        return await self._transcribe_and_respond(speech_segment)

    async def process_complete_audio(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> str:
        """Process a complete audio clip (non-streaming).

        Args:
            audio_data: Complete PCM audio data.
            sample_rate: Sample rate.
            channels: Number of channels.

        Returns:
            AI response text.
        """
        processed = AudioProcessor.prepare_for_stt(
            audio_data,
            source_sample_rate=sample_rate,
            source_channels=channels,
        )

        await self._emit(PipelineEvent.SPEECH_DETECTED)
        text = await self._transcribe_and_respond(processed)
        await self._emit(PipelineEvent.SPEECH_ENDED)
        return text

    async def _transcribe_and_respond(self, audio_data: bytes) -> str:
        """Transcribe audio, get AI response, and synthesize speech.

        Args:
            audio_data: Preprocessed PCM audio bytes.

        Returns:
            The AI response text.
        """
        if not self._stt or not self._stt.is_ready:
            await self._emit(PipelineEvent.ERROR, "STT not ready")
            return ""

        self._is_processing = True
        self._active_session.state = SessionState.PROCESSING_SPEECH
        await self._update_state(ConnectionState.PROCESSING)

        try:
            # 1. Transcribe
            await self._emit(PipelineEvent.TRANSCRIPTION_STARTED)
            transcript: STTResult = await self._stt.transcribe(
                audio_data,
                sample_rate=16000,
            )

            if transcript.is_empty:
                await self._emit(PipelineEvent.ERROR, "No speech detected")
                self._is_processing = False
                return ""

            await self._emit(PipelineEvent.TRANSCRIPTION_COMPLETE, {
                "text": transcript.text,
                "confidence": transcript.confidence,
                "language": transcript.language,
            })

            # 2. Get AI response
            await self._emit(PipelineEvent.AI_PROCESSING_STARTED)
            self._active_session.state = SessionState.WAITING_FOR_AI

            conversation_id = self._active_session.conversation_id
            response = await self._ai_engine.chat(
                message=transcript.text,
                conversation_id=conversation_id,
                stream=False,
            )

            response_text = response.content
            await self._emit(PipelineEvent.AI_RESPONSE_READY, {
                "text": response_text,
                "conversation_id": conversation_id,
            })

            # 3. Synthesize speech
            if response_text and self._tts and self._tts.is_ready and self._config.voice.tts_stream_audio:
                self._active_session.state = SessionState.SPEAKING
                await self._update_state(ConnectionState.SPEAKING)
                await self._emit(PipelineEvent.TTS_STARTED, {
                    "text": response_text[:100],
                })

                tts_result = await self._tts.synthesize(response_text)
                if tts_result.success:
                    await self._emit(PipelineEvent.TTS_COMPLETE, {
                        "audio_bytes": tts_result.audio_bytes,
                        "duration": tts_result.duration_seconds,
                        "sample_rate": tts_result.sample_rate,
                    })

            await self._emit(PipelineEvent.TURN_COMPLETE, {
                "transcript": transcript.text,
                "response": response_text,
            })

            return response_text

        except Exception as e:
            logger.error(f"Voice pipeline processing failed: {e}")
            await self._emit(PipelineEvent.ERROR, str(e))
            return ""

        finally:
            self._is_processing = False
            self._active_session.state = SessionState.IDLE
            await self._update_state(ConnectionState.CONNECTED)

    # --- Session Management ---

    async def start_session(
        self,
        conversation_id: Optional[str] = None,
    ) -> VoiceSession:
        """Start a new voice interaction session.

        Args:
            conversation_id: Optional existing conversation ID.

        Returns:
            The new VoiceSession.
        """
        self._active_session = self._session_manager.create_session(
            conversation_id=conversation_id,
        )
        self._active_session.state = SessionState.LISTENING
        await self._update_state(ConnectionState.LISTENING)
        await self._emit(PipelineEvent.LISTENING_STARTED, {
            "session_id": self._active_session.id,
        })
        logger.info(f"Voice session started: {self._active_session.id[:8]}...")
        return self._active_session

    async def end_session(self) -> None:
        """End the current voice session."""
        if self._active_session:
            self._active_session.state = SessionState.ENDED
            self._active_session.is_active = False
            await self._emit(PipelineEvent.LISTENING_STOPPED)
            await self._update_state(ConnectionState.CONNECTED)
            logger.info("Voice session ended")
            self._active_session = None

    async def interrupt(self) -> None:
        """Interrupt the current processing (e.g., user interrupts AI)."""
        if self._active_session:
            self._active_session.state = SessionState.INTERRUPTED
            self._is_processing = False
            await self._update_state(ConnectionState.LISTENING)
            await self._emit(PipelineEvent.STATE_CHANGED, "interrupted")

    @property
    def active_session(self) -> Optional[VoiceSession]:
        return self._active_session

    @property
    def is_listening(self) -> bool:
        return (
            self._active_session is not None
            and self._active_session.state == SessionState.LISTENING
        )

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    # --- Lifecycle ---

    async def shutdown(self) -> None:
        """Shut down the pipeline and release resources."""
        logger.info("Shutting down voice pipeline...")
        await self.end_session()
        if self._stt:
            await self._stt.close()
        if self._tts:
            await self._tts.close()
        if self._vad:
            await self._vad.close()
        self._is_running = False
        logger.info("Voice pipeline shut down")
