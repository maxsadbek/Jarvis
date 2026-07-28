"""WebSocket Message Handler Service.

Extracted from the monolithic handler in main.py to provide:
- Single Responsibility: Each message type handled by dedicated method
- Testability: Can be unit tested without a running server
- Type Safety: Proper typing for all message handlers
- Extensibility: Easy to add new message types
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from loguru import logger

from backend.app.api.websocket import ConnectionManager
from backend.app.config import settings
from backend.app.core.engine import AIEngine
from backend.app.models.schemas import ConnectionState, Message, MessageRole, MessageType


class MessageHandlerError(Exception):
    """Base exception for message handler errors."""


class EngineNotReadyError(MessageHandlerError):
    """Raised when the AI engine is not initialized."""


class MessageHandler:
    """Handles incoming WebSocket messages with proper routing.

    Each message type has a dedicated handler method, making the
    system easy to extend and test.
    """

    def __init__(
        self,
        engine: AIEngine,
        connection_manager: ConnectionManager,
        voice_pipeline: Any = None,
    ) -> None:
        self._engine = engine
        self._connection_manager = connection_manager
        self._voice_pipeline = voice_pipeline

        # Router: message type -> handler method
        self._handlers: dict[str, Any] = {
            "chat": self._handle_chat,
            "voice": self._handle_voice_command,
            "voice_audio": self._handle_voice_audio,
            "audio": self._handle_legacy_audio,
            "command": self._handle_command,
            "ping": self._handle_ping,
        }

    async def handle(self, client_id: str, msg_type: str, data: Any) -> None:
        """Route a message to the appropriate handler.

        Args:
            client_id: The client's unique ID.
            msg_type: The message type string.
            data: The message payload (dict or bytes).
        """
        handler = self._handlers.get(msg_type)
        if handler is None:
            logger.warning(f"Unknown message type: {msg_type}")
            await self._connection_manager.send_error(
                client_id, "unknown_type", f"Unknown message type: {msg_type}"
            )
            return

        try:
            await handler(client_id, data)
        except EngineNotReadyError:
            await self._connection_manager.send_error(
                client_id, "engine_not_ready", "Engine is initializing"
            )
        except Exception as e:
            logger.error(f"Handler error for {msg_type} (client={client_id[:8]}): {e}")
            await self._connection_manager.send_error(
                client_id, "handler_error", str(e)
            )

    # ---- Chat ----

    async def _handle_chat(self, client_id: str, data: Any) -> None:
        """Handle a text chat message."""
        if not self._engine:
            raise EngineNotReadyError("Engine not initialized")

        conversation_id = (
            self._connection_manager.get_conversation_id(client_id) or "default"
        )
        text = data.get("text", "") if isinstance(data, dict) else str(data)

        if not text.strip():
            return

        await self._connection_manager.send_state(client_id, ConnectionState.PROCESSING)

        try:
            response = await self._engine.chat(
                message=text,
                conversation_id=conversation_id,
                stream=False,
            )

            await self._connection_manager.send_text(
                client_id,
                response.content,
                {
                    "conversation_id": conversation_id,
                    "type": response.type.value,
                },
            )

            # Synthesize TTS if available
            await self._maybe_synthesize_tts(client_id, response.content)

        finally:
            await self._connection_manager.send_state(
                client_id, ConnectionState.CONNECTED
            )

    # ---- Voice Commands ----

    async def _handle_voice_command(self, client_id: str, data: Any) -> None:
        """Handle voice session commands."""
        action = data.get("action", "") if isinstance(data, dict) else ""
        params = data.get("params", {}) if isinstance(data, dict) else {}

        if action == "start_session":
            await self._start_voice_session(client_id, params)
        elif action == "end_session":
            await self._end_voice_session(client_id)
        elif action == "interrupt":
            await self._interrupt_voice(client_id)
        else:
            await self._connection_manager.send_text(
                client_id, f"Unknown voice action: {action}"
            )

    async def _start_voice_session(
        self, client_id: str, params: dict[str, Any]
    ) -> None:
        """Start a voice interaction session."""
        if not self._voice_pipeline:
            await self._connection_manager.send_error(
                client_id, "voice_unavailable", "Voice pipeline not available"
            )
            return

        conversation_id = params.get("conversation_id")
        session = await self._voice_pipeline.start_session(
            conversation_id=conversation_id
        )
        self._connection_manager.set_conversation_id(
            client_id, session.conversation_id
        )
        await self._connection_manager.send_text(
            client_id,
            f"Voice session started: {session.id[:8]}...",
            {"session_id": session.id},
        )

    async def _end_voice_session(self, client_id: str) -> None:
        """End the current voice session."""
        if self._voice_pipeline:
            await self._voice_pipeline.end_session()
        await self._connection_manager.send_text(client_id, "Voice session ended")

    async def _interrupt_voice(self, client_id: str) -> None:
        """Interrupt current voice processing."""
        if self._voice_pipeline:
            await self._voice_pipeline.interrupt()
        await self._connection_manager.send_text(client_id, "Interrupted")

    # ---- Voice Audio Processing ----

    async def _handle_voice_audio(self, client_id: str, data: Any) -> None:
        """Process audio through the voice pipeline."""
        if not isinstance(data, bytes) or len(data) == 0 or not self._voice_pipeline:
            return

        if not self._engine:
            raise EngineNotReadyError("Engine not initialized")

        conversation_id = (
            self._connection_manager.get_conversation_id(client_id) or "default"
        )

        try:
            # Ensure session is active
            if not self._voice_pipeline.active_session:
                await self._voice_pipeline.start_session(
                    conversation_id=conversation_id
                )

            # Process through pipeline
            response_text = await self._voice_pipeline.process_complete_audio(
                audio_data=data,
                sample_rate=16000,
                channels=1,
            )

            if response_text:
                await self._connection_manager.send_text(
                    client_id,
                    response_text,
                    {
                        "conversation_id": conversation_id,
                        "source": "voice",
                    },
                )

                # Synthesize and stream audio response
                await self._maybe_synthesize_tts(client_id, response_text)

        except Exception as e:
            logger.error(f"Voice pipeline processing failed: {e}")
            await self._connection_manager.send_error(
                client_id, "voice_error", str(e)
            )
        finally:
            await self._connection_manager.send_state(
                client_id, ConnectionState.CONNECTED
            )

    # ---- Legacy Audio (direct STT -> AI -> TTS) ----

    async def _handle_legacy_audio(self, client_id: str, data: Any) -> None:
        """Handle legacy audio processing (direct binary audio)."""
        if not isinstance(data, bytes) or len(data) == 0:
            return

        if not self._engine:
            raise EngineNotReadyError("Engine not initialized")

        conversation_id = (
            self._connection_manager.get_conversation_id(client_id) or "default"
        )

        await self._connection_manager.send_state(client_id, ConnectionState.PROCESSING)

        try:
            from backend.app.voice.stt import SpeechToText

            stt = SpeechToText()
            if not stt.is_ready:
                await stt.initialize()

            text = await stt.transcribe(data)
            if not text.strip():
                return

            await self._connection_manager.send_text(
                client_id, f"[Transcript: {text}]"
            )

            response = await self._engine.chat(
                message=text,
                conversation_id=conversation_id,
            )

            await self._connection_manager.send_text(
                client_id,
                response.content,
                {"conversation_id": conversation_id, "transcript": text},
            )

            await self._maybe_synthesize_tts(client_id, response.content)

        except Exception as e:
            logger.error(f"Legacy audio processing failed: {e}")
            await self._connection_manager.send_error(
                client_id, "audio_error", str(e)
            )
        finally:
            await self._connection_manager.send_state(
                client_id, ConnectionState.CONNECTED
            )

    # ---- Commands ----

    async def _handle_command(self, client_id: str, data: Any) -> None:
        """Handle client commands."""
        action = data.get("action", "") if isinstance(data, dict) else ""
        params = data.get("params", {}) if isinstance(data, dict) else {}

        if action == "set_conversation":
            conv_id = params.get("id", str(uuid.uuid4()))
            self._connection_manager.set_conversation_id(client_id, conv_id)
            await self._connection_manager.send_text(
                client_id, f"Conversation ID: {conv_id}"
            )

        elif action == "clear_memory":
            if self._engine:
                await self._engine.clear_memory()
            await self._connection_manager.send_text(client_id, "Memory cleared")

        elif action == "search_memory":
            query = params.get("query", "")
            if self._engine and query:
                results = await self._engine.search_memories(query)
                if results:
                    text = "Memory search results:\n" + "\n".join(
                        [f"- {r.content[:200]}" for r in results]
                    )
                else:
                    text = "No relevant memories found."
                await self._connection_manager.send_text(client_id, text)

    # ---- Ping ----

    async def _handle_ping(self, client_id: str, data: Any) -> None:
        """Handle ping (no-op, connection manager handles pong)."""
        pass

    # ---- TTS Helper ----

    async def _maybe_synthesize_tts(self, client_id: str, text: str) -> None:
        """Synthesize TTS audio if the voice pipeline is available.

        Args:
            client_id: The client ID to stream audio to.
            text: Text to synthesize.
        """
        if (
            not self._voice_pipeline
            or not text
            or not hasattr(self._voice_pipeline, "_tts")
        ):
            return

        tts = getattr(self._voice_pipeline, "_tts", None)
        streamer = getattr(self._voice_pipeline, "_streamer", None)

        if tts is None or streamer is None:
            return

        if not tts.is_ready:
            return

        try:
            await self._connection_manager.send_state(
                client_id, ConnectionState.SPEAKING
            )
            tts_result = await tts.synthesize(text)
            if tts_result.success:
                async for chunk in streamer.stream_wav(tts_result.audio_bytes):
                    await self._connection_manager.send_audio_chunk(
                        client_id, chunk[0]
                    )
        except Exception as e:
            logger.warning(f"TTS synthesis failed: {e}")
