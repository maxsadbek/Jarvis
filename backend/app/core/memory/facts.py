"""Important Facts System.

Extracts, stores, and manages important facts from conversations.
Uses heuristic-based extraction to identify user-provided information
that should be remembered long-term.

Fact types detected:
- Personal information (name, age, location, occupation)
- Preferences and interests
- Relationships (contacts, names)
- Plans and goals
- Technical details (project info, tech stack)
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import ImportantFact, MemoryItem


# Patterns for detecting important information in text
FACT_PATTERNS = {
    "personal": [
        r"my name is (\w+)",
        r"I(?:')?m (\w+)",
        r"I live in (\w[\w\s]*)",
        r"I(?:')?m \w+ years old",
        r"my (?:email|phone) is",
        r"I work as (?:a|an) (\w+)",
        r"my (?:job|occupation) is",
        r"I(?:')?m from (\w[\w\s]*)",
    ],
    "preference": [
        r"I (?:like|love|enjoy|prefer) (\w[\w\s]*)",
        r"I don't (?:like|enjoy) (\w[\w\s]*)",
        r"I (?:hate|dislike) (\w[\w\s]*)",
        r"my favorite (\w+) is (\w+)",
        r"I(?:')?d rather (\w[\w\s]*)",
    ],
    "goal": [
        r"I want to (\w[\w\s]*)",
        r"I(?:')?m (?:trying|working) to (\w[\w\s]*)",
        r"my goal is to (\w[\w\s]*)",
        r"I(?:')?d like to (\w[\w\s]*)",
        r"I(?:')?m planning to (\w[\w\s]*)",
    ],
    "contact": [
        r"my (?:friend|colleague|brother|sister|mom|dad|wife|husband) (\w+)",
        r"contact (\w+)",
        r"(\w+) is (?:my|our) (\w+)",
    ],
    "technical": [
        r"I(?:')?m using (\w[\w\s]*)",
        r"my (?:project|app|code) uses (\w[\w\s]*)",
        r"I(?:')?m (?:building|developing|creating) (\w[\w\s]*)",
        r"the (?:stack|framework|library) is (\w[\w\s]*)",
    ],
}


class FactsMemory:
    """Extracts, stores, and manages important facts."""

    def __init__(self) -> None:
        self._facts: dict[str, ImportantFact] = {}
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the facts memory."""
        # Try to load from persistent storage
        try:
            import json
            from pathlib import Path

            facts_file = settings.get_data_path("memory") / "facts.json"
            if facts_file.exists():
                with open(facts_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        fact = ImportantFact(**item)
                        self._facts[fact.id] = fact
                logger.info(f"Loaded {len(self._facts)} important facts")
        except Exception as e:
            logger.warning(f"Could not load saved facts: {e}")

        self._initialized = True
        return True

    async def extract_facts(self, text: str, conversation_id: Optional[str] = None) -> list[ImportantFact]:
        """Extract important facts from text using pattern matching.

        Args:
            text: The text to analyze.
            conversation_id: Optional conversation context.

        Returns:
            List of newly extracted facts.
        """
        if not text:
            return []

        new_facts = []
        text_lower = text.lower()
        text_hash = hash(text_lower)

        # Fast pre-check: skip if this exact text was already processed
        if hasattr(self, '_processed_hashes') and text_hash in self._processed_hashes:
            return []
        if not hasattr(self, '_processed_hashes'):
            self._processed_hashes = set()
        self._processed_hashes.add(text_hash)
        if len(self._processed_hashes) > 1000:
            self._processed_hashes.clear()

        # Build fast duplicate set from existing facts
        existing_normalized = {
            f.fact.lower().strip() for f in self._facts.values()
        }

        for category, patterns in FACT_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    fact_text = match.group(0).strip()
                    # Fast duplicate check
                    if fact_text.lower() in existing_normalized:
                        continue
                    # Add to set for subsequent checks
                    existing_normalized.add(fact_text.lower())

                    fact = ImportantFact(
                        id=str(uuid.uuid4()),
                        fact=fact_text,
                        category=category,
                        confidence=0.6,
                        importance=0.5,
                        source="conversation",
                        conversation_id=conversation_id,
                        context=text[:200] if len(text) > len(fact_text) else None,
                    )
                    self._facts[fact.id] = fact
                    new_facts.append(fact)
                    logger.debug(f"Extracted fact [{category}]: {fact_text}")

        # Debounce persistence: only write every 30 seconds or after 10 new facts
        if new_facts:
            self._schedule_persist()

        return new_facts

    async def add_fact(
        self,
        fact_text: str,
        category: str = "general",
        importance: float = 0.5,
        confidence: float = 0.7,
        conversation_id: Optional[str] = None,
    ) -> ImportantFact:
        """Manually add a fact.

        Args:
            fact_text: The fact to remember.
            category: Fact category.
            importance: Importance score (0-1).
            confidence: Confidence score (0-1).
            conversation_id: Optional conversation context.

        Returns:
            The created ImportantFact.
        """
        if self._is_duplicate(fact_text):
            # Update existing fact's confidence
            for fact in self._facts.values():
                if fact.fact == fact_text:
                    fact.confidence = max(fact.confidence, confidence)
                    fact.importance = max(fact.importance, importance)
                    fact.timestamp = datetime.now()
                    return fact

        fact = ImportantFact(
            id=str(uuid.uuid4()),
            fact=fact_text,
            category=category,
            importance=importance,
            confidence=confidence,
            source="manual",
            conversation_id=conversation_id,
        )
        self._facts[fact.id] = fact
        await self._persist()
        return fact

    async def verify_fact(self, fact_id: str) -> bool:
        """Mark a fact as verified by the user."""
        fact = self._facts.get(fact_id)
        if fact:
            fact.verified = True
            fact.confidence = min(1.0, fact.confidence + 0.2)
            await self._persist()
            return True
        return False

    async def get_facts(
        self,
        category: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 20,
    ) -> list[ImportantFact]:
        """Get facts, optionally filtered.

        Args:
            category: Optional category filter.
            min_importance: Minimum importance threshold.
            limit: Maximum results.

        Returns:
            List of facts sorted by importance (descending).
        """
        facts = self._facts.values()

        if category:
            facts = [f for f in facts if f.category == category]
        if min_importance > 0:
            facts = [f for f in facts if f.importance >= min_importance]

        sorted_facts = sorted(facts, key=lambda f: f.importance, reverse=True)
        return sorted_facts[:limit]

    async def get_summary_for_prompt(self) -> str:
        """Get a formatted summary of important facts for the AI prompt.

        Returns:
            A string summarizing known facts about the user.
        """
        if not self._facts:
            return ""

        sections = []
        categories = {
            "personal": "Personal Information",
            "preference": "Preferences",
            "goal": "Goals & Plans",
            "contact": "Relationships",
            "technical": "Technical Details",
            "general": "General",
        }

        for cat_key, cat_label in categories.items():
            cat_facts = [f for f in self._facts.values() if f.category == cat_key]
            if cat_facts:
                sections.append(f"{cat_label}:")
                for fact in cat_facts[:5]:  # Top 5 per category
                    prefix = "✓" if fact.verified else "•"
                    sections.append(f"  {prefix} {fact.fact}")

        return "\n".join(sections) if sections else ""

    async def search_facts(self, query: str, limit: int = 5) -> list[ImportantFact]:
        """Search facts by keyword matching.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            List of matching facts.
        """
        query_lower = query.lower()
        matches = []
        for fact in self._facts.values():
            if query_lower in fact.fact.lower():
                matches.append(fact)

        return sorted(matches, key=lambda f: f.importance, reverse=True)[:limit]

    def _is_duplicate(self, fact_text: str) -> bool:
        """Check if a fact is already stored (fuzzy match)."""
        fact_lower = fact_text.lower()
        for existing in self._facts.values():
            # Simple substring check
            if fact_lower in existing.fact.lower() or existing.fact.lower() in fact_lower:
                return True
            # Check for significant overlap
            existing_words = set(existing.fact.lower().split())
            fact_words = set(fact_lower.split())
            if len(existing_words & fact_words) >= min(3, len(fact_words)):
                intersection_ratio = len(existing_words & fact_words) / len(fact_words | existing_words)
                if intersection_ratio > 0.6:
                    return True
        return False

    def _schedule_persist(self) -> None:
        """Debounce persistence - only write after changes settle."""
        if hasattr(self, '_persist_task') and self._persist_task and not self._persist_task.done():
            return  # Already scheduled

        async def _debounced_persist():
            await asyncio.sleep(30)  # Wait 30 seconds before writing
            await self._persist()

        self._persist_task = asyncio.create_task(_debounced_persist())

    async def _persist(self) -> None:
        """Persist facts to disk."""
        try:
            import json
            facts_file = settings.get_data_path("memory") / "facts.json"
            data = [fact.model_dump() for fact in self._facts.values()]
            with open(facts_file, "w") as f:
                json.dump(data, f, default=str, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist facts: {e}")

    async def get_stats(self) -> dict[str, Any]:
        """Get facts memory statistics."""
        categories = {}
        for fact in self._facts.values():
            cat = fact.category
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_facts": len(self._facts),
            "categories": categories,
            "verified_facts": sum(1 for f in self._facts.values() if f.verified),
            "high_importance": sum(1 for f in self._facts.values() if f.importance > 0.7),
        }

    async def clear(self) -> None:
        """Clear all stored facts."""
        self._facts.clear()
        try:
            facts_file = settings.get_data_path("memory") / "facts.json"
            if facts_file.exists():
                facts_file.unlink()
        except Exception:
            pass
        logger.info("Facts memory cleared")
