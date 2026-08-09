"""Memory Manager - Unified Interface (Upgraded).

Central coordinator for all memory subsystems with:
- Permanent user profile (identity, projects, interests)
- Memory encryption for sensitive data at rest
- Privacy controls (classification, TTL, right to forget)
- Hybrid vector search (semantic + keyword)
- Importance tiers (hot/warm/cold)
- Background consolidation with TTL enforcement
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.core.memory.encryption import MemoryEncryption
from backend.app.core.memory.facts import FactsMemory
from backend.app.core.memory.habits import HabitsMemory
from backend.app.core.memory.preferences import UserPreferences
from backend.app.core.memory.privacy import PrivacyControls
from backend.app.core.memory.retrieval import MemoryRetrieval
from backend.app.core.memory.short_term import ShortTermMemory
from backend.app.core.memory.summarizer import ConversationSummarizer
from backend.app.core.memory.user_profile import UserProfile
from backend.app.core.memory.vector import VectorMemory
from backend.app.models.schemas import (
    ConversationSummary,
    ImportantFact,
    MemoryItem,
    MemoryQuery,
    Message,
    MessageRole,
    UserHabit,
    UserPreference,
)


class MemoryManager:
    """Unified memory manager - upgraded with privacy, encryption, profile.

    Memory subsystems:
    - UserProfile: Permanent identity, projects, interests
    - ShortTermMemory: Recent conversation buffer
    - VectorMemory: ChromaDB with hybrid search, encryption, tiers
    - UserPreferences: Persistent key-value store
    - FactsMemory: Extracted important facts
    - HabitsMemory: Learned user patterns
    - PrivacyControls: Classification, TTL, right to forget
    - MemoryEncryption: AES-256-GCM for sensitive data
    """

    def __init__(self) -> None:
        # New subsystems
        self._user_profile: Optional[UserProfile] = None
        self._encryption: Optional[MemoryEncryption] = None
        self._privacy: Optional[PrivacyControls] = None

        # Existing subsystems
        self._short_term: Optional[ShortTermMemory] = None
        self._vector: Optional[VectorMemory] = None
        self._preferences: Optional[UserPreferences] = None
        self._facts: Optional[FactsMemory] = None
        self._habits: Optional[HabitsMemory] = None
        self._summarizer: Optional[ConversationSummarizer] = None
        self._retrieval: Optional[MemoryRetrieval] = None

        self._consolidation_task: Optional[asyncio.Task] = None
        self._is_consolidating = False
        self._start_time = datetime.now()

    async def initialize(self, llm_provider=None) -> bool:
        """Initialize all memory subsystems with privacy-first order."""
        logger.info("Initializing upgraded memory system...")

        try:
            # 1. Encryption (needed by other subsystems)
            self._encryption = MemoryEncryption()
            enc_ok = await self._encryption.initialize()
            if enc_ok:
                logger.info("  ✓ Memory encryption ready")
            else:
                logger.info("  - Memory encryption not available (cryptography not installed)")

            # 2. Privacy controls (needs to be early for classification)
            self._privacy = PrivacyControls()
            priv_ok = await self._privacy.initialize()
            logger.info("  ✓ Privacy controls ready")

            # 3. User profile (permanent identity)
            self._user_profile = UserProfile()
            profile_ok = await self._user_profile.initialize()
            logger.info(f"  ✓ User profile ready")

            # 4. Short-term memory (always available)
            self._short_term = ShortTermMemory()
            logger.info("  ✓ Short-term memory ready")

            # 5. Vector memory with encryption and privacy
            self._vector = VectorMemory()
            try:
                import asyncio
                logger.info("  - Vector memory initialize boshlanmoqda (15s timeout)...")
                vector_ok = await asyncio.wait_for(
                    self._vector.initialize(
                        encryption=self._encryption,
                        privacy=self._privacy,
                    ),
                    timeout=15.0
                )
                logger.info(f"  ✓ Vector memory initialized (status: {vector_ok})")
            except asyncio.TimeoutError:
                logger.warning("  ✗ Vector memory initialization TIMEOUT (15s). Falling back to degraded memory.")
                vector_ok = False
            except Exception as ex:
                logger.warning(f"  ✗ Vector memory failed to initialize: {ex}. Falling back to degraded memory.")
                vector_ok = False

            # 6. User preferences
            self._preferences = UserPreferences()
            pref_ok = await self._preferences.initialize()

            # 7. Important facts
            self._facts = FactsMemory()
            facts_ok = await self._facts.initialize()

            # 8. User habits
            self._habits = HabitsMemory()
            habits_ok = await self._habits.initialize()

            # 9. Conversation summarizer
            self._summarizer = ConversationSummarizer(llm_provider=llm_provider)

            # 10. Retrieval orchestrator (with profile + privacy)
            self._retrieval = MemoryRetrieval(
                vector_memory=self._vector,
                short_term=self._short_term,
                facts=self._facts,
                preferences=self._preferences,
                habits=self._habits,
                user_profile=self._user_profile,
                privacy=self._privacy,
            )

            self._start_consolidation()

            logger.info("✓ Upgraded memory system initialized")
            return True

        except Exception as e:
            logger.error(f"Memory system initialization failed: {e}")
            return False

    # --- Message Processing ---

    async def process_message(self, message: Message, conversation_id: str) -> None:
        """Process message through all subsystems with privacy controls."""
        # 1. Short-term
        if self._short_term:
            self._short_term.add_message(message, conversation_id)

        # 2. Vector memory (with encryption for sensitive content)
        if self._vector:
            await self._vector.store_message(message, conversation_id)

        # 3. Facts extraction (with privacy class detection)
        if self._facts and message.role == MessageRole.USER:
            facts = await self._facts.extract_facts(message.content, conversation_id)
            if self._vector and facts:
                for fact in facts:
                    # Detect privacy class
                    privacy_class = "private"
                    if self._privacy:
                        pc = self._privacy.classify_content(fact.fact)
                        privacy_class = pc.value

                    await self._vector.store(
                        content=f"Fact ({fact.category}): {fact.fact}",
                        metadata={
                            "fact_id": fact.id,
                            "category": fact.category,
                            "confidence": str(fact.confidence),
                        },
                        memory_type="fact",
                        importance=fact.importance,
                        category=fact.category,
                        privacy_class=privacy_class,
                    )

            # Update user profile from facts
            if self._user_profile:
                for fact in facts:
                    if fact.category == "personal":
                        # Try to extract name
                        import re
                        name_match = re.search(r"my name is (\w+)", fact.fact.lower())
                        if name_match:
                            await self._user_profile.set_field("name", name_match.group(1).title())

                    elif fact.category == "preference":
                        interest_match = re.search(r"i (?:like|love|enjoy) (\w[\w\s]*)", fact.fact.lower())
                        if interest_match:
                            await self._user_profile.add_interest(interest_match.group(1).strip())

                    elif fact.category == "goal":
                        goal_match = re.search(r"i want to (\w[\w\s]*)", fact.fact.lower())
                        if goal_match:
                            await self._user_profile.add_goal(goal_match.group(1).strip())

        # 4. Habit learning
        if self._habits and message.role == MessageRole.USER:
            hour = datetime.now().hour
            await self._habits.observe(message.content, hour)

    # --- Context Building ---

    async def get_context(
        self,
        conversation_id: str,
        current_message: str,
    ) -> list[Message]:
        """Build context with user profile, privacy-filtered memories."""
        context_messages: list[Message] = []

        # 1. User profile (identity, projects, interests)
        if self._user_profile:
            try:
                profile_text = await self._user_profile.get_full_context()
                if profile_text.strip():
                    context_messages.append(
                        Message(
                            role=MessageRole.SYSTEM,
                            content=f"[User Profile]\n{profile_text}",
                            metadata={"type": "user_profile"},
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to get user profile: {e}")

        # 2. Personalized context from all memory systems (privacy-filtered)
        if self._retrieval:
            try:
                context_text = await self._retrieval.get_relevant_context(
                    user_message=current_message,
                    conversation_id=conversation_id,
                )
                if context_text.strip():
                    context_messages.append(
                        Message(
                            role=MessageRole.SYSTEM,
                            content=f"[Personal Context]\n{context_text}",
                            metadata={"type": "personal_context"},
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to build personal context: {e}")

        # 3. Recent conversation history
        if self._short_term:
            try:
                history = self._short_term.get_recent_messages(
                    conversation_id=conversation_id,
                    limit=30,
                )
                context_messages.extend(history)
            except Exception as e:
                logger.warning(f"Failed to get conversation history: {e}")

        # 4. Current user message
        context_messages.append(
            Message(
                role=MessageRole.USER,
                content=current_message,
            )
        )

        return context_messages

    # --- Search ---

    async def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[MemoryItem]:
        if self._retrieval:
            mem_query = MemoryQuery(
                query=query,
                limit=limit,
                threshold=threshold,
            )
            result = await self._retrieval.search(mem_query)
            return result.items
        return []

    # --- User Profile ---

    async def get_profile(self) -> UserProfile:
        """Get the user profile manager."""
        if not self._user_profile:
            raise RuntimeError("User profile not initialized")
        return self._user_profile

    async def get_profile_summary(self) -> str:
        """Get user profile summary for the AI."""
        if self._user_profile:
            return await self._user_profile.get_full_context()
        return ""

    async def get_active_projects(self) -> list[Any]:
        """Get the user's active projects."""
        if self._user_profile:
            return await self._user_profile.get_active_projects()
        return []

    async def add_project(
        self,
        name: str,
        description: str = "",
        tech_stack: list[str] | None = None,
        status: str = "active",
    ) -> Any:
        """Add a project to the user's profile."""
        if self._user_profile:
            return await self._user_profile.add_project(
                name=name,
                description=description,
                tech_stack=tech_stack,
                status=status,
            )
        raise RuntimeError("User profile not initialized")

    # --- Preferences ---

    async def get_preference(self, key: str, default: Any = None) -> Any:
        if self._preferences:
            return await self._preferences.get(key, default)
        return default

    async def set_preference(self, key: str, value: Any) -> UserPreference:
        if self._preferences:
            return await self._preferences.set(key, value)
        raise RuntimeError("Preferences not initialized")

    async def get_all_preferences(self) -> dict[str, UserPreference]:
        if self._preferences:
            return await self._preferences.get_all()
        return {}

    async def set_preferences(self, prefs: dict[str, Any]) -> list[UserPreference]:
        if self._preferences:
            return await self._preferences.set_many(prefs)
        return []

    # --- Facts ---

    async def get_facts(
        self,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> list[ImportantFact]:
        if self._facts:
            return await self._facts.get_facts(category=category, limit=limit)
        return []

    async def add_fact(
        self,
        fact_text: str,
        category: str = "general",
        importance: float = 0.5,
    ) -> Optional[ImportantFact]:
        if self._facts:
            return await self._facts.add_fact(
                fact_text=fact_text,
                category=category,
                importance=importance,
            )
        return None

    async def verify_fact(self, fact_id: str) -> bool:
        if self._facts:
            return await self._facts.verify_fact(fact_id)
        return False

    # --- Habits ---

    async def get_habits(
        self,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> list[UserHabit]:
        if self._habits:
            return await self._habits.get_habits(
                category=category,
                min_confidence=min_confidence,
            )
        return []

    # --- Summarization ---

    async def summarize_conversation(
        self,
        messages: list[Message],
        conversation_id: str,
    ) -> Optional[ConversationSummary]:
        if self._summarizer:
            return await self._summarizer.summarize(messages, conversation_id)
        return None

    async def needs_summarization(self, messages: list[Message]) -> bool:
        if self._summarizer:
            return await self._summarizer.needs_summarization(messages)
        return False

    # --- Privacy Controls ---

    async def get_privacy_controls(self) -> PrivacyControls:
        """Get the privacy controls manager."""
        if not self._privacy:
            raise RuntimeError("Privacy controls not initialized")
        return self._privacy

    async def forget_memory(self, content_key: str) -> None:
        """Request deletion of a memory (right to forget)."""
        if self._privacy:
            await self._privacy.request_deletion(content_key)
            logger.info(f"Memory deletion requested: {content_key[:100]}")

    async def forget_category(self, category: str) -> int:
        """Delete all memories in a category."""
        if self._privacy:
            await self._privacy.request_bulk_deletion(category)
        count = 0
        if self._vector:
            count = await self._vector.delete_by_filter(category=category)
        if category == "facts" and self._facts:
            await self._facts.clear()
        return count

    # --- Consolidation ---

    def _start_consolidation(self) -> None:
        if self._consolidation_task is None or self._consolidation_task.done():
            self._consolidation_task = asyncio.create_task(self._consolidation_loop())
            logger.debug("Memory consolidation started")

    async def _consolidation_loop(self) -> None:
        """Background loop: enforce TTLs, clean stale, update tiers."""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self._consolidate()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Consolidation cycle failed: {e}")

    async def _consolidate(self) -> None:
        if self._is_consolidating:
            return
        self._is_consolidating = True

        try:
            if self._short_term:
                removed = self._short_term.cleanup_stale(max_idle_minutes=120)
                if removed > 0:
                    logger.debug(f"Cleaned {removed} stale conversations")

            if self._habits and self._short_term:
                convs = self._short_term.get_all_conversations()
                for conv in convs:
                    if len(conv.messages) > 20:
                        await self._habits.observe(
                            conv.messages[-1].content,
                            datetime.now().hour,
                        )

            self._is_consolidating = False

        except Exception as e:
            logger.warning(f"Consolidation failed: {e}")
            self._is_consolidating = False

    # --- Stats ---

    async def get_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
        }

        if self._short_term:
            stats["short_term"] = self._short_term.get_stats()
        if self._vector:
            stats["vector"] = await self._vector.get_stats()
        if self._preferences:
            stats["preferences"] = await self._preferences.get_stats()
        if self._facts:
            stats["facts"] = await self._facts.get_stats()
        if self._habits:
            stats["habits"] = await self._habits.get_stats()
        if self._user_profile:
            stats["user_profile"] = await self._user_profile.get_stats()
        if self._privacy:
            stats["privacy"] = await self._privacy.get_stats()
        if self._encryption:
            stats["encryption"] = await self._encryption.get_stats()

        return stats

    async def clear(self) -> None:
        logger.info("Clearing all memories...")
        if self._short_term:
            await self._short_term.clear()
        if self._vector:
            await self._vector.clear()
        if self._preferences:
            await self._preferences.clear()
        if self._facts:
            await self._facts.clear()
        if self._habits:
            await self._habits.clear()
        if self._user_profile:
            await self._user_profile.clear_profile()
        logger.info("All memories cleared")

    async def clear_conversations(self) -> None:
        if self._short_term:
            await self._short_term.clear()
        if self._vector:
            self._vector._messages.clear()
        logger.info("Conversation history cleared")

    async def shutdown(self) -> None:
        logger.info("Shutting down memory system...")
        if self._consolidation_task and not self._consolidation_task.done():
            self._consolidation_task.cancel()
            try:
                await self._consolidation_task
            except asyncio.CancelledError:
                pass
        logger.info("Memory system shut down")
