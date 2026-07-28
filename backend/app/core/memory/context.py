"""Context Manager.

Builds the context window for LLM requests by combining:
- System prompt
- Recent conversation history
- Relevant past memories
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from backend.app.config import settings
from backend.app.core.memory.vector import VectorMemory
from backend.app.models.schemas import Message, MessageRole


class ContextManager:
    """Manages conversation context for the AI engine."""

    def __init__(self, memory_backend: Optional[VectorMemory] = None) -> None:
        self._memory = memory_backend
        self._max_history = 50  # Max messages to keep in context
        self._max_memory_results = 5  # Max memory results to include

    async def build_context(
        self,
        conversation_id: str,
        current_message: str,
    ) -> list[Message]:
        """Build the full context for an LLM request.

        Args:
            conversation_id: Current conversation ID.
            current_message: The user's current message.

        Returns:
            List of messages forming the complete context.
        """
        messages: list[Message] = []

        # 1. Add relevant past memories (long-term context)
        if self._memory and settings.MEMORY_ENABLED:
            try:
                memories = await self._memory.search(
                    query=current_message,
                    limit=self._max_memory_results,
                    threshold=settings.MEMORY_RELEVANCE_THRESHOLD,
                )
                if memories:
                    memory_context = "Relevant past memories:\n"
                    for m in memories:
                        memory_context += f"- [{m.timestamp.strftime('%Y-%m-%d %H:%M')}] {m.content[:200]}\n"
                    messages.append(
                        Message(
                            role=MessageRole.SYSTEM,
                            content=memory_context,
                            metadata={"type": "memory_context"},
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to retrieve memories: {e}")

        # 2. Add recent conversation history
        if self._memory:
            try:
                history = await self._memory.get_conversation_history(
                    conversation_id=conversation_id,
                    limit=self._max_history,
                )
                messages.extend(history)
            except Exception as e:
                logger.warning(f"Failed to get conversation history: {e}")

        # 3. Add the current user message
        messages.append(
            Message(
                role=MessageRole.USER,
                content=current_message,
            )
        )

        return messages

    async def extract_key_points(self, text: str) -> list[str]:
        """Extract key points from a text for memory storage."""
        # Simple extraction - can be enhanced with NLP later
        sentences = text.replace("\n", " ").split(".")
        key_points = [
            s.strip() for s in sentences
            if len(s.strip()) > 30 and "I" in s or "you" in s or "remember" in s
        ]
        return key_points[:3]
