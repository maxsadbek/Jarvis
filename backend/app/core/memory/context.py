"""Context Manager.

Builds the context window for LLM requests by combining:
- Personalized user context (preferences, facts, habits)
- Recent conversation history
- Relevant past memories
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.core.memory.manager import MemoryManager
from backend.app.models.schemas import Message, MessageRole


class ContextManager:
    """Manages conversation context for the AI engine.

    Uses the MemoryManager to build personalized context
    with preferences, facts, habits, and relevant memories.
    """

    def __init__(self, memory_manager: Optional[MemoryManager] = None) -> None:
        self._memory = memory_manager

    async def build_context(
        self,
        conversation_id: str,
        current_message: str,
    ) -> list[Message]:
        """Build the full context for an LLM request.

        Uses the MemoryManager's get_context() for personalized
        context with preferences, facts, habits, and memories.

        Args:
            conversation_id: Current conversation ID.
            current_message: The user's current message.

        Returns:
            List of messages forming the complete context.
        """
        messages: list[Message] = []

        if self._memory and settings.MEMORY_ENABLED:
            try:
                # Use MemoryManager to get full personalized context
                context = await self._memory.get_context(
                    conversation_id=conversation_id,
                    current_message=current_message,
                )
                messages.extend(context)
                return messages
            except Exception as e:
                logger.warning(f"Failed to build memory context: {e}")

        # Fallback: add the user message directly
        messages.append(
            Message(
                role=MessageRole.USER,
                content=current_message,
            )
        )

        return messages
