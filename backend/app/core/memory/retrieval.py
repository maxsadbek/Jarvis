"""Memory Retrieval System - Upgraded.

Intelligently retrieves relevant memories using multiple strategies:
1. Hybrid search (semantic + keyword)
2. User profile context (identity, projects, interests)
3. Privacy-filtered (respect deletion requests and TTL)
4. Importance-tiered (hot/warm/cold)
5. Recency and frequency boosted

Privacy: All retrieval respects user deletion requests and TTL.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from loguru import logger

from backend.app.core.memory.facts import FactsMemory
from backend.app.core.memory.habits import HabitsMemory
from backend.app.core.memory.preferences import UserPreferences
from backend.app.core.memory.privacy import PrivacyControls
from backend.app.core.memory.short_term import ShortTermMemory
from backend.app.core.memory.user_profile import UserProfile
from backend.app.core.memory.vector import MemoryTier, VectorMemory
from backend.app.models.schemas import (
    MemoryItem,
    MemoryQuery,
    MemorySearchResult,
)


class MemoryRetrieval:
    """Orchestrates memory retrieval with privacy and personalization.

    Retrieval pipeline:
    1. User profile context (identity, projects, interests)
    2. Hybrid vector search (semantic + keyword)
    3. Keyword search through facts and preferences
    4. Privacy filtering (respect deletion requests)
    5. Importance-tiered ranking (hot/warm/cold)
    """

    def __init__(
        self,
        vector_memory: Optional[VectorMemory] = None,
        short_term: Optional[ShortTermMemory] = None,
        facts: Optional[FactsMemory] = None,
        preferences: Optional[UserPreferences] = None,
        habits: Optional[HabitsMemory] = None,
        user_profile: Optional[UserProfile] = None,
        privacy: Optional[PrivacyControls] = None,
    ) -> None:
        self._vector = vector_memory
        self._short_term = short_term
        self._facts = facts
        self._preferences = preferences
        self._habits = habits
        self._user_profile = user_profile
        self._privacy = privacy

    async def search(self, query: MemoryQuery) -> MemorySearchResult:
        """Hybrid search across all memory systems with privacy filtering.

        Args:
            query: The memory query with filters.

        Returns:
            Ranked, privacy-filtered search results.
        """
        start_time = time.time()
        all_items: list[MemoryItem] = []
        strategies_used: list[str] = []

        # Strategy 1: Hybrid vector search (semantic + keyword)
        if self._vector and self._vector._initialized:
            try:
                vector_items = await self._vector.search(
                    query=query.query,
                    limit=query.limit,
                    threshold=query.threshold,
                    memory_types=query.memory_types,
                    categories=query.categories,
                    min_importance=query.min_importance,
                    hybrid=True,
                )
                all_items.extend(vector_items)
                strategies_used.append("hybrid_vector")
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # Strategy 2: Keyword search through facts
        if self._facts:
            try:
                fact_items = await self._keyword_search_facts(query)
                all_items.extend(fact_items)
                strategies_used.append("facts_keyword")
            except Exception as e:
                logger.warning(f"Fact search failed: {e}")

        # Strategy 3: Preference matching
        if self._preferences:
            try:
                pref_items = await self._keyword_search_preferences(query)
                all_items.extend(pref_items)
                strategies_used.append("preferences")
            except Exception as e:
                logger.warning(f"Preference search failed: {e}")

        # Strategy 4: Habit matching
        if self._habits:
            try:
                habit_items = await self._keyword_search_habits(query)
                all_items.extend(habit_items)
                strategies_used.append("habits")
            except Exception as e:
                logger.warning(f"Habit search failed: {e}")

        # Filter: Respect privacy deletion requests
        if self._privacy:
            all_items = await self._filter_deleted(all_items)

        # Rank with importance tiers
        ranked = self._rank_results(all_items, query)

        elapsed = (time.time() - start_time) * 1000

        return MemorySearchResult(
            items=ranked[: query.limit],
            total_results=len(ranked),
            query_time_ms=elapsed,
            strategies_used=strategies_used,
        )

    async def get_relevant_context(
        self,
        user_message: str,
        conversation_id: str,
    ) -> str:
        """Get the most relevant context - now with user profile and privacy.

        Args:
            user_message: The user's current message.
            conversation_id: Current conversation ID.

        Returns:
            Formatted, privacy-filtered context string.
        """
        context_parts = []

        # 1. Permanent user profile (identity, projects, interests)
        if self._user_profile:
            try:
                profile_context = await self._user_profile.get_full_context()
                if profile_context:
                    context_parts.append("**User Profile:**")
                    context_parts.append(profile_context)
            except Exception as e:
                logger.warning(f"Failed to get user profile: {e}")

        # 2. Relevant memories via hybrid vector search
        query = MemoryQuery(query=user_message, limit=5, threshold=0.4)
        search_result = await self.search(query)
        if search_result.items:
            memory_section = "**Relevant Past Memories:**\n"
            for item in search_result.items:
                age = self._format_age(item.timestamp)
                tier = item.metadata.get("tier", "cold")
                tier_mark = "🔥" if tier == "hot" else "⭐" if tier == "warm" else "•"
                memory_section += f"  {tier_mark} [{age}] {item.content[:200]}\n"
            context_parts.append(memory_section)

        # 3. Important known facts (privacy-filtered)
        if self._facts:
            try:
                facts_text = await self._facts.get_summary_for_prompt()
                if facts_text:
                    context_parts.append(f"**Known Facts:**\n{facts_text}")
            except Exception as e:
                logger.warning(f"Failed to get facts: {e}")

        # 4. User preferences (only non-default)
        if self._preferences:
            try:
                pref_text = await self._preferences.get_summary_for_prompt()
                if pref_text:
                    context_parts.append(f"**Preferences:**\n{pref_text}")
            except Exception as e:
                logger.warning(f"Failed to get preferences: {e}")

        # 5. Learned habits (high confidence only)
        if self._habits:
            try:
                habits_text = await self._habits.get_summary_for_prompt()
                if habits_text:
                    context_parts.append(habits_text)
            except Exception as e:
                logger.warning(f"Failed to get habits: {e}")

        return "\n\n".join(context_parts)

    async def _filter_deleted(self, items: list[MemoryItem]) -> list[MemoryItem]:
        """Remove items that the user has requested to delete."""
        if not self._privacy:
            return items

        filtered = []
        for item in items:
            # Check if the content or ID has been marked for deletion
            is_deleted = await self._privacy.is_deletion_requested(item.id)
            if not is_deleted:
                is_deleted = await self._privacy.is_deletion_requested(item.content[:100])
            if not is_deleted:
                filtered.append(item)

        return filtered

    async def _keyword_search_facts(self, query: MemoryQuery) -> list[MemoryItem]:
        if not self._facts:
            return []
        facts = await self._facts.search_facts(query.query, limit=query.limit)
        return [
            MemoryItem(
                id=f.id,
                content=f.fact,
                type="fact",
                timestamp=f.timestamp,
                metadata={
                    "category": f.category,
                    "confidence": f.confidence,
                    "importance": f.importance,
                    "verified": f.verified,
                    "tier": "hot" if f.importance > 0.7 else "warm",
                },
                relevance_score=f.confidence,
                importance=f.importance,
                category=f.category,
            )
            for f in facts
        ]

    async def _keyword_search_preferences(self, query: MemoryQuery) -> list[MemoryItem]:
        if not self._preferences:
            return []
        query_lower = query.query.lower()
        items: list[MemoryItem] = []
        prefs = await self._preferences.get_all()

        for key, pref in prefs.items():
            if query_lower in key.lower() or query_lower in str(pref.value).lower():
                items.append(
                    MemoryItem(
                        id=key,
                        content=f"Preference: {key} = {pref.value}",
                        type="preference",
                        timestamp=pref.updated_at,
                        metadata={"category": pref.category, "tier": "warm"},
                        relevance_score=0.7,
                        importance=0.4,
                        category=pref.category,
                    )
                )
        return items

    async def _keyword_search_habits(self, query: MemoryQuery) -> list[MemoryItem]:
        if not self._habits:
            return []
        habits = await self._habits.get_habits(min_confidence=0.3)
        query_lower = query.query.lower()
        items: list[MemoryItem] = []

        for habit in habits:
            if query_lower in habit.pattern.lower():
                items.append(
                    MemoryItem(
                        id=habit.id,
                        content=f"Habit: {habit.pattern}",
                        type="habit",
                        timestamp=habit.last_observed,
                        metadata={
                            "confidence": habit.confidence,
                            "category": habit.category,
                            "tier": "warm" if habit.confidence > 0.7 else "cold",
                        },
                        relevance_score=habit.confidence,
                        importance=habit.confidence * 0.8,
                        category=habit.category,
                    )
                )
        return items

    def _rank_results(
        self,
        items: list[MemoryItem],
        query: MemoryQuery,
    ) -> list[MemoryItem]:
        """Rank with importance tiers and recency boost."""
        seen: set[str] = set()
        ranked: list[MemoryItem] = []

        for item in items:
            content_key = item.content[:100].lower()
            if content_key in seen:
                continue
            seen.add(content_key)

            if query.categories and item.category not in query.categories:
                continue
            if query.memory_types and item.type not in query.memory_types:
                continue
            if query.min_importance and item.importance < query.min_importance:
                continue

            tier = MemoryTier.tier_score(item.metadata.get("tier", "cold"))
            final_score = item.relevance_score * 0.4
            final_score += item.importance * 0.3
            final_score += tier * 0.2
            final_score += self._recency_bonus(item) * 0.1

            item.relevance_score = min(1.0, final_score)
            ranked.append(item)

        return sorted(ranked, key=lambda x: x.relevance_score, reverse=True)

    def _recency_bonus(self, item: MemoryItem) -> float:
        import datetime
        now = datetime.datetime.now()
        if not item.timestamp:
            return 0

        age_hours = (now - item.timestamp).total_seconds() / 3600

        if age_hours < 1:
            return 1.0
        elif age_hours < 24:
            return 0.8
        elif age_hours < 168:
            return 0.5
        elif age_hours < 720:
            return 0.3
        else:
            return 0.1

    def _format_age(self, timestamp) -> str:
        import datetime
        if not timestamp:
            return "unknown"

        now = datetime.datetime.now()
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.datetime.fromisoformat(timestamp)
            except ValueError:
                return "unknown"

        diff = now - timestamp
        if diff.total_seconds() < 60:
            return "just now"
        elif diff.total_seconds() < 3600:
            mins = int(diff.total_seconds() / 60)
            return f"{mins}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}h ago"
        elif diff.days < 30:
            return f"{diff.days}d ago"
        elif diff.days < 365:
            months = diff.days // 30
            return f"{months}mo ago"
        else:
            years = diff.days // 365
            return f"{years}y ago"



