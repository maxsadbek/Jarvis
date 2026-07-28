"""AI Engine - The Brain of JARVIS.

Orchestrates all AI operations:
- Routes requests to the appropriate LLM provider
- Manages conversation context and memory
- Coordinates tool execution
- Handles voice transcription and synthesis
"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.core.llm.base import LLMProvider
from backend.app.core.llm.openrouter import OpenRouterProvider
from backend.app.core.llm.local import LocalLLMProvider
from backend.app.core.memory.context import ContextManager
from backend.app.core.memory.vector import VectorMemory
from backend.app.models.schemas import (
    ConnectionState,
    Message,
    MessageRole,
    MessageType,
    SystemStatus,
)
from backend.app.tools.base import ToolRegistry


class AIEngine:
    """Core AI engine orchestrating LLM, memory, and tools."""

    def __init__(self) -> None:
        self._llm_provider: Optional[LLMProvider] = None
        self._memory: Optional[VectorMemory] = None
        self._context_manager: Optional[ContextManager] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._start_time: float = time.time()
        self._state: ConnectionState = ConnectionState.DISCONNECTED

    async def initialize(self) -> None:
        """Initialize all engine components."""
        logger.info("Initializing JARVIS AI Engine...")

        # 1. Initialize LLM provider
        if settings.OPENROUTER_API_KEY:
            logger.info("Connecting to OpenRouter...")
            self._llm_provider = OpenRouterProvider()
            await self._llm_provider.initialize()
            if self._llm_provider.is_available:
                logger.info(f"✓ Connected to {self._llm_provider.provider_name}")

        # Fallback to local LLM
        if (not self._llm_provider or not self._llm_provider.is_available) and settings.USE_LOCAL_LLM:
            logger.info("Trying local Ollama...")
            self._llm_provider = LocalLLMProvider()
            await self._llm_provider.initialize()
            if self._llm_provider.is_available:
                logger.info(f"✓ Connected to {self._llm_provider.provider_name}")

        if not self._llm_provider or not self._llm_provider.is_available:
            logger.warning("No LLM provider available")

        # 2. Initialize memory
        if settings.MEMORY_ENABLED:
            logger.info("Initializing memory system...")
            self._memory = VectorMemory()
            initialized = await self._memory.initialize()
            if initialized:
                logger.info("✓ Memory system ready")
            else:
                logger.warning("Memory system not available")

        # 3. Initialize context manager
        self._context_manager = ContextManager(self._memory)
        logger.info("✓ Context manager ready")

        # 4. Initialize tool registry
        if settings.TOOLS_ENABLED:
            self._tool_registry = ToolRegistry()
            await self._tool_registry.initialize()
            logger.info(f"✓ Tool registry ready with {len(self._tool_registry.tools)} tools")

        logger.info("JARVIS AI Engine initialization complete")

    @property
    def state(self) -> ConnectionState:
        return self._state

    @state.setter
    def state(self, new_state: ConnectionState) -> None:
        self._state = new_state
        logger.debug(f"State changed to: {new_state.value}")

    @property
    def is_llm_ready(self) -> bool:
        return self._llm_provider is not None and self._llm_provider.is_available

    async def chat(
        self,
        message: str,
        conversation_id: str,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> Message | AsyncGenerator[str, None]:
        """Process a chat message and return AI response.

        Args:
            message: The user's message.
            conversation_id: The conversation ID.
            stream: Whether to stream the response.
            model: Optional model override.

        Returns:
            Either a Message or an async generator for streaming.
        """
        if not self.is_llm_ready:
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content="JARVIS AI engine is not initialized. Please check configuration and try again.",
                metadata={"conversation_id": conversation_id},
            )

        self.state = ConnectionState.PROCESSING

        # Build conversation context
        context_messages = await self._context_manager.build_context(
            conversation_id=conversation_id,
            current_message=message,
        )

        # Store user message
        user_msg = Message(
            role=MessageRole.USER,
            content=message,
            metadata={"conversation_id": conversation_id},
        )
        if self._memory:
            await self._memory.store_message(user_msg, conversation_id)

        if stream:
            return self._stream_response(context_messages, conversation_id, model)
        else:
            # Get full response
            response = await self._llm_provider.chat(
                messages=context_messages,
                model=model,
            )
            response.metadata["conversation_id"] = conversation_id

            # Store assistant response
            if self._memory:
                await self._memory.store_message(response, conversation_id)

            self.state = ConnectionState.CONNECTED
            return response

    async def _stream_response(
        self,
        messages: list[Message],
        conversation_id: str,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response token by token."""
        full_response = ""
        try:
            async for token in self._llm_provider.chat_stream(
                messages=messages,
                model=model,
            ):
                full_response += token
                yield token
        finally:
            # Store the complete response
            if self._memory and full_response:
                response_msg = Message(
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    metadata={"conversation_id": conversation_id},
                )
                await self._memory.store_message(response_msg, conversation_id)
            self.state = ConnectionState.CONNECTED

    async def get_status(self) -> SystemStatus:
        """Get the current system status."""
        import psutil

        return SystemStatus(
            llm_connected=self.is_llm_ready,
            llm_model=settings.OPENROUTER_MODEL if self.is_llm_ready else None,
            stt_ready=True,
            tts_ready=True,
            memory_ready=self._memory is not None and self._memory._initialized,
            tools_loaded=list(self._tool_registry.tools.keys()) if self._tool_registry else [],
            cpu_usage=psutil.cpu_percent(interval=0.1),
            memory_usage=psutil.virtual_memory().percent,
            uptime_seconds=time.time() - self._start_time,
        )

    async def get_memory_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        if self._memory:
            return await self._memory.get_stats()
        return {"error": "Memory not available"}

    async def clear_memory(self) -> bool:
        """Clear all memories."""
        if self._memory:
            await self._memory.clear()
            return True
        return False

    async def search_memories(self, query: str, limit: int = 5) -> list[Any]:
        """Search stored memories."""
        if self._memory:
            return await self._memory.search(query=query, limit=limit)
        return []

    async def shutdown(self) -> None:
        """Gracefully shut down the engine."""
        logger.info("Shutting down JARVIS engine...")
        if hasattr(self._llm_provider, "close"):
            await self._llm_provider.close()
        self.state = ConnectionState.DISCONNECTED
        logger.info("JARVIS engine shutdown complete")
