"""User Habits System.

Learns and remembers user patterns and habits over time.
Detects recurring behaviors, preferences, and communication patterns
from conversation history.

Habit types detected:
- Communication patterns (greetings, formality, language)
- Work patterns (coding languages, tools, project types)
- Schedule patterns (when the user is active)
- Recurring requests (common topics the user asks about)
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import UserHabit


class HabitsMemory:
    """Learns and tracks user habits and patterns over time."""

    def __init__(self) -> None:
        self._habits: dict[str, UserHabit] = {}
        self._observations: list[dict[str, Any]] = []  # Raw observations for pattern detection
        self._initialized = False

        # Pattern detectors
        self._topic_counter: Counter = Counter()
        self._time_activity: dict[int, int] = defaultdict(int)  # Hour of day -> activity count
        self._greeting_patterns: list[str] = []

    async def initialize(self) -> bool:
        """Load saved habits from persistent storage."""
        try:
            import json
            habits_file = settings.get_data_path("memory") / "habits.json"
            if habits_file.exists():
                with open(habits_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        habit = UserHabit(**item)
                        self._habits[habit.id] = habit
                logger.info(f"Loaded {len(self._habits)} learned habits")
        except Exception as e:
            logger.warning(f"Could not load habits: {e}")

        self._initialized = True
        return True

    async def observe(self, user_message: str, hour_of_day: int) -> Optional[UserHabit]:
        """Observe a user action and detect patterns.

        Args:
            user_message: The user's message text.
            hour_of_day: Hour when the message was sent (0-23).

        Returns:
            A new UserHabit if a pattern was detected, None otherwise.
        """
        if not user_message:
            return None

        message_lower = user_message.lower().strip()

        # Track activity time
        self._time_activity[hour_of_day] += 1

        # Track topics (significant words)
        words = message_lower.split()
        significant_words = [w for w in words if len(w) > 3]
        for word in significant_words[:5]:
            self._topic_counter[word] += 1

        # Detect greeting patterns
        greetings = ["hello", "hi", "hey", "good morning", "good evening", "yo"]
        if any(g in message_lower for g in greetings):
            self._greeting_patterns.append(message_lower[:50])

        # Record observation
        self._observations.append({
            "text": message_lower[:100],
            "hour": hour_of_day,
            "timestamp": datetime.now().isoformat(),
        })

        # Run periodic pattern detection
        if len(self._observations) % 5 == 0:  # Every 5 observations
            return await self._detect_new_patterns()

        return None

    async def _detect_new_patterns(self) -> Optional[UserHabit]:
        """Run pattern detection algorithms to identify new habits.

        Returns:
            A new UserHabit if a strong pattern is detected.
        """
        # 1. Detect active hours
        if sum(self._time_activity.values()) > 10:
            most_active_hour = max(self._time_activity, key=self._time_activity.get)
            peak_count = self._time_activity[most_active_hour]
            total = sum(self._time_activity.values())
            peak_ratio = peak_count / total

            if peak_ratio > 0.3:  # User is active mostly in one time window
                period = "morning" if 5 <= most_active_hour < 12 else \
                         "afternoon" if 12 <= most_active_hour < 17 else \
                         "evening" if 17 <= most_active_hour < 22 else "night"
                pattern_text = f"User is most active during the {period} (around {most_active_hour}:00)"

                if not self._has_similar_habit(pattern_text):
                    return await self._create_habit(
                        pattern=pattern_text,
                        category="schedule",
                        confidence=peak_ratio,
                    )

        # 2. Detect recurring topics
        if len(self._topic_counter) > 20:
            top_topics = self._topic_counter.most_common(5)
            for topic, count in top_topics:
                if count >= 3 and not self._has_similar_habit(f"topic: {topic}"):
                    return await self._create_habit(
                        pattern=f"User frequently discusses topics related to '{topic}' ({count} times)",
                        category="communication",
                        confidence=min(1.0, count / 10),
                    )

        # 3. Detect greeting style
        if len(self._greeting_patterns) >= 3:
            greeting_counter = Counter(self._greeting_patterns)
            most_common_greeting, count = greeting_counter.most_common(1)[0]
            if count >= 2:
                pattern_text = f"User typically starts conversations with: '{most_common_greeting}'"
                if not self._has_similar_habit(pattern_text):
                    return await self._create_habit(
                        pattern=pattern_text,
                        category="communication",
                        confidence=min(1.0, count / 5),
                    )

        return None

    async def _create_habit(
        self,
        pattern: str,
        category: str,
        confidence: float,
    ) -> UserHabit:
        """Create and store a new habit.

        Args:
            pattern: Description of the detected pattern.
            category: Habit category.
            confidence: Confidence in the pattern (0-1).

        Returns:
            The created UserHabit.
        """
        habit = UserHabit(
            id=str(uuid.uuid4()),
            pattern=pattern,
            category=category,
            confidence=confidence,
            frequency=1,
        )
        self._habits[habit.id] = habit
        logger.info(f"Learned habit [{category}]: {pattern}")
        await self._persist()
        return habit

    async def reinforce(self, habit_id: str) -> bool:
        """Reinforce a habit (called when pattern is observed again).

        Args:
            habit_id: The habit to reinforce.

        Returns:
            True if reinforced, False if not found.
        """
        habit = self._habits.get(habit_id)
        if not habit:
            return False

        habit.frequency += 1
        habit.confidence = min(1.0, habit.confidence + 0.1)
        habit.last_observed = datetime.now()
        await self._persist()
        return True

    async def get_habits(
        self,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list[UserHabit]:
        """Get habits, optionally filtered.

        Args:
            category: Optional category filter.
            min_confidence: Minimum confidence threshold.
            limit: Maximum results.

        Returns:
            List of habits sorted by confidence (descending).
        """
        habits = self._habits.values()

        if category:
            habits = [h for h in habits if h.category == category]
        if min_confidence > 0:
            habits = [h for h in habits if h.confidence >= min_confidence]

        return sorted(habits, key=lambda h: h.confidence, reverse=True)[:limit]

    def _has_similar_habit(self, pattern: str) -> bool:
        """Check if a similar habit already exists."""
        pattern_lower = pattern.lower()
        for habit in self._habits.values():
            if pattern_lower in habit.pattern.lower() or habit.pattern.lower() in pattern_lower:
                return True
            # Word overlap check
            pattern_words = set(pattern_lower.split())
            habit_words = set(habit.pattern.lower().split())
            if len(pattern_words & habit_words) / max(len(pattern_words | habit_words), 1) > 0.5:
                return True
        return False

    async def get_summary_for_prompt(self) -> str:
        """Get a formatted summary of learned habits for the AI prompt.

        Returns:
            A string summarizing known habits.
        """
        habits = await self.get_habits(min_confidence=0.5)
        if not habits:
            return ""

        lines = ["User Habits & Patterns:"]
        for habit in habits:
            confidence_pct = f"{habit.confidence * 100:.0f}%"
            lines.append(f"• {habit.pattern} (confidence: {confidence_pct}, observed {habit.frequency}x)")

        return "\n".join(lines)

    async def get_stats(self) -> dict[str, Any]:
        """Get habits memory statistics."""
        categories = {}
        for habit in self._habits.values():
            cat = habit.category
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_habits": len(self._habits),
            "categories": categories,
            "high_confidence": sum(1 for h in self._habits.values() if h.confidence > 0.7),
            "total_observations": len(self._observations),
        }

    async def _persist(self) -> None:
        """Persist habits to disk."""
        try:
            import json
            habits_file = settings.get_data_path("memory") / "habits.json"
            data = [habit.model_dump() for habit in self._habits.values()]
            with open(habits_file, "w") as f:
                json.dump(data, f, default=str, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist habits: {e}")

    async def clear(self) -> None:
        """Clear all learned habits."""
        self._habits.clear()
        self._observations.clear()
        self._topic_counter.clear()
        self._time_activity.clear()
        self._greeting_patterns.clear()
        try:
            habits_file = settings.get_data_path("memory") / "habits.json"
            if habits_file.exists():
                habits_file.unlink()
        except Exception:
            pass
        logger.info("Habits memory cleared")
