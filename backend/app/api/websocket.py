"""WebSocket Manager.

Handles real-time bidirectional communication between the frontend
and the JARVIS AI engine. Supports:
- Voice streaming (audio chunks)
- Text chat with streaming responses
- State updates
- Audio playback streaming
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from backend.app.models.schemas import (
    ConnectionState,
    WSMessage,
    AudioChunkMessage,
    ResponseMessage,
    StateMessage,
)


class ConnectionManager:
    """Manages WebSocket connections to the JARVIS engine."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_states: dict[str, ConnectionState] = {}
        self.connection_metadata: dict[str, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_states[client_id] = ConnectionState.CONNECTED
        self.connection_metadata[client_id] = {
            "connected_at": time.time(),
            "user_agent": websocket.headers.get("user-agent", "unknown"),
            "conversation_id": None,
        }
        logger.info(f"Client connected: {client_id}")

        # Send initial state
        await self.send_state(client_id, ConnectionState.CONNECTED)

    async def disconnect(self, client_id: str) -> None:
        """Disconnect a client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_states:
            del self.connection_states[client_id]
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
        logger.info(f"Client disconnected: {client_id}")

    async def send_message(self, client_id: str, message: WSMessage) -> None:
        """Send a WebSocket message to a specific client."""
        if client_id not in self.active_connections:
            return

        try:
            await self.active_connections[client_id].send_json(
                message.model_dump()
            )
        except Exception as e:
            logger.error(f"Failed to send message to {client_id}: {e}")

    async def send_text(self, client_id: str, text: str, metadata: Optional[dict] = None) -> None:
        """Send a text response message."""
        message = ResponseMessage(
            type="response",
            data={
                "text": text,
                "is_final": True,
                **(metadata or {}),
            },
        )
        await self.send_message(client_id, message)

    async def send_state(self, client_id: str, state: ConnectionState) -> None:
        """Send a connection state update."""
        if client_id in self.connection_states:
            self.connection_states[client_id] = state

        message = StateMessage(
            type="state",
            data={"state": state.value},
        )
        await self.send_message(client_id, message)

    async def send_audio_chunk(self, client_id: str, audio_chunk: bytes) -> None:
        """Send an audio chunk for playback."""
        import base64

        message = AudioChunkMessage(
            type="audio",
            data={
                "chunk": base64.b64encode(audio_chunk).decode(),
                "format": "wav",
                "sample_rate": 22050,
            },
        )
        await self.send_message(client_id, message)

    async def send_error(self, client_id: str, error_code: str, error_message: str) -> None:
        """Send an error message."""
        from backend.app.models.schemas import ErrorMessage

        message = ErrorMessage(
            type="error",
            data={"code": error_code, "message": error_message},
        )
        await self.send_message(client_id, message)

    async def broadcast(self, message: WSMessage) -> None:
        """Send a message to all connected clients."""
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message)

    async def handle_client(
        self,
        websocket: WebSocket,
        client_id: str,
        on_message_callback: Any,
    ) -> None:
        """Handle a client's WebSocket connection lifecycle.

        Args:
            websocket: The WebSocket connection.
            client_id: Unique client identifier.
            on_message_callback: Async callback to handle incoming messages.
                Signature: async def callback(client_id, message_type, data)
        """
        await self.connect(websocket, client_id)

        try:
            while True:
                # Receive message (supporting both text and bytes)
                raw_data = await websocket.receive()

                if "text" in raw_data:
                    # Text message (JSON)
                    try:
                        data = json.loads(raw_data["text"])
                        msg_type = data.get("type", "unknown")
                        msg_data = data.get("data", {})

                        if msg_type == "ping":
                            await self.send_message(client_id, WSMessage(
                                type="pong",
                                data={"timestamp": time.time()},
                            ))
                        else:
                            await on_message_callback(client_id, msg_type, msg_data)

                    except json.JSONDecodeError:
                        await self.send_error(client_id, "parse_error", "Invalid JSON message")

                elif "bytes" in raw_data:
                    # Binary data (audio chunks)
                    await on_message_callback(client_id, "audio", raw_data["bytes"])

        except WebSocketDisconnect:
            logger.info(f"Client disconnected normally: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
        finally:
            await self.disconnect(client_id)

    def get_conversation_id(self, client_id: str) -> Optional[str]:
        """Get the active conversation ID for a client."""
        meta = self.connection_metadata.get(client_id)
        return meta.get("conversation_id") if meta else None

    def set_conversation_id(self, client_id: str, conversation_id: str) -> None:
        """Set the active conversation ID for a client."""
        if client_id in self.connection_metadata:
            self.connection_metadata[client_id]["conversation_id"] = conversation_id

    @property
    def active_count(self) -> int:
        """Number of active connections."""
        return len(self.active_connections)

    def get_state(self, client_id: str) -> ConnectionState:
        """Get client's connection state."""
        return self.connection_states.get(client_id, ConnectionState.DISCONNECTED)
