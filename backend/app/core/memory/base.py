"""Abstract base class for memory backends.

Defines the interface for storing and retrieving long-term memories.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from backend.app.models.schemas import Message, MemoryItem


class MemoryBackend(ABC):
    """Abstract base for memory storage backends."""

    @abstractmethod
    async def store(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        embedding: Optional[list[float]] = None,
    ) -> str:
        """Store a memory item.

        Args:
            content: The text content to remember.
            metadata: Optional metadata (conversation_id, timestamp, etc.).
            embedding: Optional pre-computed embedding vector.

        Returns:
            Memory item ID.
        """
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.5,
    ) -> list[MemoryItem]:
        """Search for relevant memories.

        Args:
            query: Search query text.
            limit: Maximum number of results.
            threshold: Minimum relevance score (0-1).

        Returns:
            List of relevant memory items.
        """
        ...

    @abstractmethod
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """Get messages from a specific conversation.

        Args:
            conversation_id: The conversation ID.
            limit: Maximum number of messages.

        Returns:
            List of conversation messages.
        """
        ...

    @abstractmethod
    async def store_message(self, message: Message, conversation_id: str) -> None:
        """Store a single message in conversation history.

        Args:
            message: The message to store.
            conversation_id: Conversation this message belongs to.
        """
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored memories."""
        ...

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics.

        Returns:
            Dict with stats like total items, conversations, etc.
        """
        ...
