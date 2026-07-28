"""User Preferences Store.

Persistent key-value storage for user preferences.
Supports categories, descriptions, and change tracking.
Preferences are automatically loaded at startup and
persisted to disk using TinyDB for portability.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import UserPreference


# Default preferences with descriptions
DEFAULT_PREFERENCES: dict[str, tuple[Any, str, str]] = {
    # General
    "user_name": ("", "general", "Your preferred name"),
    "language": ("en", "general", "Preferred language for responses"),
    "timezone": ("UTC", "general", "Your timezone"),
    "date_format": ("YYYY-MM-DD", "general", "Preferred date format"),
    "time_format": ("24h", "general", "Preferred time format (12h/24h)"),
    # Voice
    "voice_speed": (1.0, "voice", "Speech speed (0.5-2.0)"),
    "voice_wake_word": ("jarvis", "voice", "Wake word for activation"),
    "voice_tts_enabled": (True, "voice", "Enable text-to-speech responses"),
    # Appearance
    "theme": ("dark", "appearance", "UI theme (dark/light)"),
    "font_size": ("medium", "appearance", "UI font size"),
    # Privacy
    "share_usage_data": (False, "privacy", "Share anonymous usage data"),
    "store_conversations": (True, "privacy", "Store conversation history"),
    "auto_delete_days": (90, "privacy", "Auto-delete conversations after N days"),
    # AI
    "ai_model": ("", "ai", "Preferred AI model override"),
    "ai_temperature": (0.7, "ai", "AI response creativity"),
    "ai_max_tokens": (2048, "ai", "Maximum response length"),
    "ai_personality": ("professional", "ai", "AI personality (professional/casual/creative)"),
}


class UserPreferences:
    """Persistent user preferences store with TinyDB."""

    def __init__(self) -> None:
        self._db = None
        self._table = None
        self._preferences: dict[str, UserPreference] = {}
        self._initialized = False

    async def initialize(self) -> bool:
        """Load preferences from persistent storage."""
        try:
            from tinydb import TinyDB, Query

            db_path = settings.get_data_path("memory") / "preferences.json"
            self._db = TinyDB(str(db_path))
            self._table = self._db.table("user_preferences")
            Pref = Query()

            # Load all stored preferences
            for item in self._table.all():
                pref = UserPreference(**item)
                self._preferences[pref.key] = pref

            # Ensure defaults exist
            for key, (default_value, category, description) in DEFAULT_PREFERENCES.items():
                if key not in self._preferences:
                    pref = UserPreference(
                        key=key,
                        value=default_value,
                        category=category,
                        description=description,
                    )
                    self._preferences[key] = pref
                    self._table.upsert(
                        pref.model_dump(),
                        Pref.key == key,
                    )

            self._initialized = True
            logger.info(f"User preferences loaded ({len(self._preferences)} items)")
            return True

        except ImportError:
            logger.warning("tinydb not installed, using in-memory preferences")
            self._initialized = True
            # Load defaults into memory
            for key, (default_value, category, description) in DEFAULT_PREFERENCES.items():
                self._preferences[key] = UserPreference(
                    key=key,
                    value=default_value,
                    category=category,
                    description=description,
                )
            return True
        except Exception as e:
            logger.error(f"Failed to load preferences: {e}")
            return False

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value by key.

        Args:
            key: Preference key.
            default: Default value if not found.

        Returns:
            Preference value.
        """
        pref = self._preferences.get(key)
        if pref:
            pref.access_count += 1  # Track for habits
            return pref.value
        return default

    async def get_preference(self, key: str) -> Optional[UserPreference]:
        """Get the full preference object."""
        return self._preferences.get(key)

    async def get_all(self) -> dict[str, UserPreference]:
        """Get all preferences."""
        return dict(self._preferences)

    async def get_by_category(self, category: str) -> dict[str, UserPreference]:
        """Get all preferences in a category."""
        return {
            k: v for k, v in self._preferences.items()
            if v.category == category
        }

    async def set(self, key: str, value: Any) -> UserPreference:
        """Set a preference value.

        Args:
            key: Preference key.
            value: New value.

        Returns:
            The updated UserPreference.
        """
        now = datetime.now()
        if key in self._preferences:
            pref = self._preferences[key]
            pref.value = value
            pref.updated_at = now
        else:
            # Infer category from known defaults
            default_info = DEFAULT_PREFERENCES.get(key, (value, "general", ""))
            pref = UserPreference(
                key=key,
                value=value,
                category=default_info[1],
                description=default_info[2],
            )
            self._preferences[key] = pref

        # Persist
        try:
            if self._table:
                from tinydb import Query
                self._table.upsert(pref.model_dump(), Query().key == key)
        except Exception as e:
            logger.warning(f"Failed to persist preference '{key}': {e}")

        logger.debug(f"Preference set: {key} = {value}")
        return pref

    async def set_many(self, preferences: dict[str, Any]) -> list[UserPreference]:
        """Set multiple preferences at once.

        Args:
            preferences: Dict of key-value pairs.

        Returns:
            List of updated UserPreference objects.
        """
        return [await self.set(key, value) for key, value in preferences.items()]

    async def delete(self, key: str) -> bool:
        """Delete a preference.

        Args:
            key: Preference key to delete.

        Returns:
            True if deleted, False if not found.
        """
        if key in self._preferences:
            del self._preferences[key]
            try:
                if self._table:
                    from tinydb import Query
                    self._table.remove(Query().key == key)
            except Exception:
                pass
            return True
        return False

    async def get_summary_for_prompt(self) -> str:
        """Get a formatted summary of user preferences for the AI prompt.

        Returns:
            A string summarizing the user's preferences.
        """
        if not self._preferences:
            return ""

        lines = ["User Preferences:"]
        for key, pref in self._preferences.items():
            # Skip defaults that haven't been changed
            default_info = DEFAULT_PREFERENCES.get(key)
            if default_info and pref.value == default_info[0]:
                continue
            lines.append(f"- {key}: {pref.value}")

        return "\n".join(lines) if len(lines) > 1 else ""

    async def get_stats(self) -> dict[str, Any]:
        """Get preference statistics."""
        categories = {}
        for pref in self._preferences.values():
            cat = pref.category
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_preferences": len(self._preferences),
            "categories": categories,
            "custom_preferences": sum(
                1 for k, v in self._preferences.items()
                if k not in DEFAULT_PREFERENCES
            ),
        }

    async def clear(self) -> None:
        """Reset all preferences to defaults."""
        self._preferences.clear()
        for key, (default_value, category, description) in DEFAULT_PREFERENCES.items():
            self._preferences[key] = UserPreference(
                key=key,
                value=default_value,
                category=category,
                description=description,
            )
        try:
            if self._db:
                self._db.drop_table("user_preferences")
                self._table = self._db.table("user_preferences")
                from tinydb import Query
                for pref in self._preferences.values():
                    self._table.upsert(pref.model_dump(), Query().key == pref.key)
        except Exception:
            pass
        logger.info("Preferences reset to defaults")
