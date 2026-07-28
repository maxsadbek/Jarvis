"""Short-Term Memory (Working Memory).

Maintains recent conversation context and working state.
Automatically summarizes and forgets old contexts using
a sliding window approach with importance-based retention.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

from backend.app.models.schemas import Message, MessageRole


@dataclass
class ShortTermMemoryConfig:
    """Configuration for short-term memory."""

    max_recent_messages: int = 50  # Messages kept in active memory
    max_conversations: int = 10  # Active conversations tracked
    context_window_seconds: int = 3600  # 1 hour before summarization
    importance_decay_minutes: int = 30  # How fast importance decays
    working_memory_size: int = 20  # Working memory buffer size


class ShortTermMemory:
    """Short-term memory with sliding window and importance decay.

    Maintains:
    - Active conversation buffer (recent messages)
    - Working memory (current task context)
    - Conversation metadata (titles, topics, active state)

    Automatically forgets/compresses old context based on
    recency and importance.
    """

    def __init__(self, config: Optional[ShortTermMemoryConfig] = None) -> None:
        self._config = config or ShortTermMemoryConfig()
        self._conversations: OrderedDict[str, ConversationBuffer] = OrderedDict()
        self._working_memory: dict[str, Any] = {}  # Current task/context state
        self._initialized = True

    # --- Conversation Buffer ---

    def add_message(self, message: Message, conversation_id: str) -> None:
        """Add a message to the conversation buffer.

        Automatically manages the sliding window and evicts
        old conversations when the limit is reached.
        """
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = ConversationBuffer(
                conversation_id=conversation_id,
            )

        conv = self._conversations[conversation_id]
        conv.messages.append(message)
        conv.last_activity = datetime.now()
        conv.message_count += 1

        # Update title from first user message
        if conv.title == "New Conversation" and message.role == MessageRole.USER:
            conv.title = message.content[:80] + ("..." if len(message.content) > 80 else "")

        # Manage sliding window - keep only most recent messages
        if len(conv.messages) > self._config.max_recent_messages:
            # Keep the first message (context) and the most recent ones
            first_msg = conv.messages[0]
            conv.messages = (
                [first_msg] +
                conv.messages[-(self._config.max_recent_messages - 1):]
            )

        # Recent conversations track
        self._conversations.move_to_end(conversation_id)

        # Evict oldest conversation if over limit
        if len(self._conversations) > self._config.max_conversations:
            oldest = next(iter(self._conversations))
            if oldest != conversation_id:  # Don't evict active one
                self._conversations.pop(oldest)

    def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 30,
    ) -> list[Message]:
        """Get recent messages from a conversation."""
        conv = self._conversations.get(conversation_id)
        if not conv:
            return []
        return conv.messages[-limit:]

    def get_conversation(self, conversation_id: str) -> Optional[ConversationBuffer]:
        """Get full conversation buffer."""
        return self._conversations.get(conversation_id)

    def get_all_conversations(self) -> list[ConversationBuffer]:
        """Get all tracked conversations, most recent first."""
        return list(reversed(list(self._conversations.values())))

    def get_active_conversation_ids(self) -> list[str]:
        """Get conversation IDs active within the context window."""
        cutoff = datetime.now() - timedelta(seconds=self._config.context_window_seconds)
        return [
            cid for cid, conv in self._conversations.items()
            if conv.last_activity > cutoff
        ]

    # --- Working Memory ---

    def set_working_context(self, key: str, value: Any) -> None:
        """Store a value in working memory (current task context)."""
        self._working_memory[key] = {
            "value": value,
            "timestamp": time.time(),
        }
        # Manage working memory size
        if len(self._working_memory) > self._config.working_memory_size:
            oldest_key = min(
                self._working_memory.keys(),
                key=lambda k: self._working_memory[k]["timestamp"],
            )
            del self._working_memory[oldest_key]

    def get_working_context(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from working memory."""
        entry = self._working_memory.get(key)
        if entry:
            return entry["value"]
        return default

    def get_all_working_context(self) -> dict[str, Any]:
        """Get all working memory context."""
        return {
            k: v["value"] for k, v in self._working_memory.items()
        }

    def clear_working_context(self) -> None:
        """Clear working memory."""
        self._working_memory.clear()

    # --- Maintenance ---

    def cleanup_stale(self, max_idle_minutes: int = 60) -> int:
        """Remove stale conversations from short-term memory.

        Args:
            max_idle_minutes: Max idle time before removal.

        Returns:
            Number of conversations removed.
        """
        cutoff = datetime.now() - timedelta(minutes=max_idle_minutes)
        stale_ids = [
            cid for cid, conv in self._conversations.items()
            if conv.last_activity < cutoff
        ]
        for cid in stale_ids:
            del self._conversations[cid]
        return len(stale_ids)

    def get_stats(self) -> dict[str, Any]:
        """Get short-term memory statistics."""
        return {
            "active_conversations": len(self._conversations),
            "total_messages_in_buffer": sum(
                len(c.messages) for c in self._conversations.values()
            ),
            "working_memory_items": len(self._working_memory),
        }

    async def clear(self) -> None:
        """Clear all short-term memory."""
        self._conversations.clear()
        self._working_memory.clear()
        logger.info("Short-term memory cleared")


@dataclass
class ConversationBuffer:
    """In-memory buffer for a single conversation."""

    conversation_id: str
    title: str = "New Conversation"
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    topics: list[str] = field(default_factory=list)
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
