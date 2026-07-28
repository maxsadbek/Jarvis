"""Conversation Summarizer.

Compresses long conversations into summaries for efficient memory storage.
Uses the LLM provider for intelligent summarization when available,
with a fallback extractive approach.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import (
    ConversationSummary,
    Message,
    MessageRole,
)


class ConversationSummarizer:
    """Summarizes conversations for efficient memory storage.

    Uses a hybrid approach:
    1. LLM-based abstractive summarization (when LLM is available)
    2. Extractive fallback (keyword frequency, sentence scoring)
    """

    def __init__(self, llm_provider=None) -> None:
        self._llm = llm_provider
        self._min_messages_for_summary = 10  # Don't summarize short chats
        self._max_summary_length = 500  # Max chars in a summary

    async def summarize(
        self,
        messages: list[Message],
        conversation_id: str,
    ) -> Optional[ConversationSummary]:
        """Summarize a list of messages.

        Args:
            messages: Messages to summarize.
            conversation_id: Conversation identifier.

        Returns:
            ConversationSummary or None if too short.
        """
        if len(messages) < self._min_messages_for_summary:
            return None

        # Extract user messages for context
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]

        # Try LLM-based summarization first
        if self._llm and self._llm.is_available:
            try:
                return await self._llm_summarize(messages, conversation_id)
            except Exception as e:
                logger.warning(f"LLM summarization failed, using extractive: {e}")

        # Fall back to extractive summarization
        return await self._extractive_summarize(messages, conversation_id)

    async def _llm_summarize(
        self,
        messages: list[Message],
        conversation_id: str,
    ) -> ConversationSummary:
        """Use LLM to generate an abstractive summary."""
        # Build conversation text
        conversation_text = ""
        for msg in messages[-50:]:  # Last 50 messages max
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            conversation_text += f"{role}: {msg.content}\n"

        summary_prompt = (
            "Summarize the key points from this conversation. "
            "Focus on: user information revealed, tasks requested, decisions made, "
            "and important context. Be concise.\n\n"
            f"{conversation_text}"
        )

        # Use the LLM to summarize
        summary_msg = await self._llm.chat(
            messages=[
                Message(role=MessageRole.SYSTEM, content="You are a conversation summarizer. Extract key points concisely."),
                Message(role=MessageRole.USER, content=summary_prompt),
            ],
        )

        summary_text = summary_msg.content[:self._max_summary_length]

        # Extract key points (split by lines/bullets)
        key_points = [
            line.strip().lstrip("- •*").strip()
            for line in summary_text.split("\n")
            if line.strip() and len(line.strip()) > 20
        ][:10]

        # Detect topics
        topics = await self._extract_topics(conversation_text)

        start_time = messages[0].timestamp if messages else datetime.now()
        end_time = messages[-1].timestamp if messages else datetime.now()

        return ConversationSummary(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            summary=summary_text,
            key_points=key_points,
            topics=topics,
            message_count=len(messages),
            start_time=start_time,
            end_time=end_time,
        )

    async def _extractive_summarize(
        self,
        messages: list[Message],
        conversation_id: str,
    ) -> ConversationSummary:
        """Extractive summarization using keyword frequency.

        Selects the most important sentences/concepts from the conversation.
        """
        # Count word frequency (excluding common words)
        word_counts: dict[str, int] = {}
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "can", "shall", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below", "between",
            "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
            "neither", "each", "every", "all", "any", "few", "more", "most",
            "other", "some", "such", "no", "only", "own", "same", "than",
            "too", "very", "just", "also", "if", "then", "else", "when",
            "where", "why", "how", "what", "which", "who", "whom", "this",
            "that", "these", "those", "i", "me", "my", "myself", "we", "our",
            "you", "your", "it", "its", "they", "them", "their", "he", "she",
            "his", "her", "him",
        }

        for msg in messages:
            if msg.role == MessageRole.USER:
                words = msg.content.lower().split()
                for word in words:
                    word = word.strip(".,!?;:'\"()[]{}").strip()
                    if word and len(word) > 3 and word not in stop_words:
                        word_counts[word] = word_counts.get(word, 0) + 1

        # Get top keywords
        top_keywords = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        # Generate summary from first user message context
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        first_relevant = ""
        for msg in messages:
            if msg.role == MessageRole.USER and len(msg.content) > 20:
                first_relevant = msg.content[:150]
                break

        summary = f"Conversation about: {', '.join(k for k, v in top_keywords[:5])}."
        if first_relevant:
            summary += f" Started with: {first_relevant}"

        # Extract key points (long user messages)
        key_points = [
            msg.content[:150] for msg in messages[-10:]
            if msg.role == MessageRole.USER and len(msg.content) > 40
        ][:5]

        topics = [k for k, v in top_keywords[:8]]
        start_time = messages[0].timestamp if messages else datetime.now()
        end_time = messages[-1].timestamp if messages else datetime.now()

        return ConversationSummary(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            summary=summary[:self._max_summary_length],
            key_points=key_points,
            topics=topics,
            message_count=len(messages),
            start_time=start_time,
            end_time=end_time,
        )

    async def _extract_topics(self, text: str) -> list[str]:
        """Extract conversation topics from text."""
        words = text.lower().split()
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "i", "you",
                      "he", "she", "it", "we", "they", "to", "of", "in", "for",
                      "on", "with", "at", "by", "from", "and", "but", "or"}

        # Count significant words
        word_counts: dict[str, int] = {}
        for word in words:
            word = word.strip(".,!?;:'\"()[]{}")
            if word and len(word) > 4 and word not in stop_words:
                word_counts[word] = word_counts.get(word, 0) + 1

        # Return top topics
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [w for w, c in sorted_words[:10]]

    async def needs_summarization(self, messages: list[Message]) -> bool:
        """Check if a conversation needs summarization.

        Args:
            messages: List of messages to check.

        Returns:
            True if the conversation exceeds summarization thresholds.
        """
        if len(messages) < self._min_messages_for_summary:
            return False

        # Check total character length
        total_chars = sum(len(m.content) for m in messages)
        return total_chars > 5000

    async def should_summarize_old(
        self,
        last_activity: datetime,
        message_count: int,
    ) -> bool:
        """Check if an old conversation should be summarized.

        Args:
            last_activity: When the conversation was last active.
            message_count: How many messages in the conversation.

        Returns:
            True if the conversation should be summarized.
        """
        age = datetime.now() - last_activity
        return age > timedelta(hours=1) and message_count > self._min_messages_for_summary
