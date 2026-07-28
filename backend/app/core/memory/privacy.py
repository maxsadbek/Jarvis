"""Privacy Controls for Memory System.

Provides:
- Data classification tiers (public, private, sensitive)
- TTL-based auto-deletion for temporary data
- Selective memory deletion (right to forget)
- Audit log of memory access
- User-facing privacy controls

Privacy is a first-class concern in the memory architecture.
Every memory item has a privacy class that determines:
- Whether it gets encrypted at rest
- How long it's retained
- Who can access it (future: multi-user)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings


class PrivacyClass(str, Enum):
    """Privacy classification for memory items.

    PUBLIC: Non-sensitive, general knowledge (e.g., "Python is a language")
    PRIVATE: Personal but not sensitive (e.g., "User likes coffee")
    SENSITIVE: Personally identifiable or sensitive (e.g., "User's email is x@y.com")
    SECRET: Highly sensitive, encrypted always (e.g., API keys, passwords)
    """

    PUBLIC = "public"
    PRIVATE = "private"
    SENSITIVE = "sensitive"
    SECRET = "secret"

    @property
    def requires_encryption(self) -> bool:
        return self in (PrivacyClass.SENSITIVE, PrivacyClass.SECRET)

    @property
    def default_ttl_days(self) -> Optional[int]:
        """Default retention period in days. None = forever."""
        return {
            PrivacyClass.PUBLIC: None,      # Keep forever
            PrivacyClass.PRIVATE: 365 * 2,  # 2 years
            PrivacyClass.SENSITIVE: 90,     # 90 days
            PrivacyClass.SECRET: 7,         # 7 days (prompt user to re-enter)
        }.get(self)


class PrivacyControls:
    """Manages privacy classification, retention, and deletion of memory data.

    Every memory operation checks with PrivacyControls for:
    - What privacy class applies
    - Whether the data should be encrypted
    - When the data should be auto-deleted
    - Whether the user has requested deletion (right to forget)
    """

    def __init__(self) -> None:
        self._initialized = False
        self._deletion_requests: set[str] = set()  # Keys/content IDs to forget
        self._access_log: list[dict[str, Any]] = []
        self._settings: dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Load privacy settings and deletion requests."""
        try:
            privacy_file = settings.get_data_path("memory") / "privacy.json"
            if privacy_file.exists():
                with open(privacy_file, "r") as f:
                    data = json.load(f)
                    self._deletion_requests = set(data.get("deletion_requests", []))
                    self._settings = data.get("settings", {})
                logger.info(f"Privacy controls loaded ({len(self._deletion_requests)} deletion requests)")

            # Default settings
            self._settings.setdefault("auto_delete_enabled", True)
            self._settings.setdefault("encrypt_sensitive", True)
            self._settings.setdefault("log_access", False)
            self._settings.setdefault("max_retention_days", 365 * 5)  # 5 years max

        except Exception as e:
            logger.warning(f"Could not load privacy settings: {e}")
            self._settings = {"auto_delete_enabled": True, "encrypt_sensitive": True}

        self._initialized = True
        return True

    # --- Classification ---

    def classify_content(self, content: str) -> PrivacyClass:
        """Detect the privacy class of content based on patterns.

        Args:
            content: The text content to classify.

        Returns:
            Appropriate PrivacyClass.
        """
        content_lower = content.lower()

        # SECRET: API keys, passwords, tokens, credentials
        secret_patterns = [
            "api_key", "api key", "password", "secret", "token",
            "credential", "private_key", "auth_token", "bearer",
            "-----begin", "ssh-rsa", "ssh-ed25519",
            "jwt", "access_key", "secret_key",
        ]
        if any(p in content_lower for p in secret_patterns):
            return PrivacyClass.SECRET

        # SENSITIVE: Email, phone, address, SSN, credit card
        import re
        if re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', content):  # Email
            return PrivacyClass.SENSITIVE
        if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', content):  # Phone
            return PrivacyClass.SENSITIVE
        if re.search(r'\b\d{5}(?:-\d{4})?\b', content):  # ZIP code
            return PrivacyClass.SENSITIVE

        # PRIVATE: Personal preferences, opinions
        private_patterns = [
            "my name is", "i live", "i work", "i like", "i love",
            "my favorite", "i prefer", "my email", "my phone",
            "i enjoy", "i hate", "i dislike",
        ]
        if any(p in content_lower for p in private_patterns):
            return PrivacyClass.PRIVATE

        return PrivacyClass.PUBLIC

    def get_ttl(self, privacy_class: PrivacyClass) -> Optional[datetime]:
        """Get the TTL (time-to-live) for a privacy class.

        Args:
            privacy_class: The privacy classification.

        Returns:
            Expiry datetime, or None if no expiry.
        """
        if not self._settings.get("auto_delete_enabled", True):
            return None

        days = privacy_class.default_ttl_days
        if days is None:
            return None

        # Apply global max retention cap
        max_days = self._settings.get("max_retention_days", 365 * 5)
        capped_days = min(days, max_days)

        return datetime.now() + timedelta(days=capped_days)

    def should_encrypt(self, privacy_class: PrivacyClass) -> bool:
        """Check if content with this privacy class should be encrypted."""
        if not self._settings.get("encrypt_sensitive", True):
            return False
        return privacy_class.requires_encryption

    # --- Right to Forget ---

    async def request_deletion(self, content_key: str) -> None:
        """Request deletion of a specific memory item (right to forget).

        Args:
            content_key: Identifier of the content to forget.
        """
        self._deletion_requests.add(content_key)
        await self._persist()
        logger.info(f"Deletion requested for: {content_key}")

    async def request_bulk_deletion(self, category: str) -> int:
        """Request deletion of all items in a category.

        Args:
            category: Category to clear (e.g., 'conversations', 'facts', 'preferences').

        Returns:
            Number of items affected (approximate).
        """
        self._deletion_requests.add(f"category:{category}:*")
        await self._persist()
        logger.info(f"Bulk deletion requested for category: {category}")
        return -1  # Exact count depends on storage

    async def is_deletion_requested(self, content_key: str) -> bool:
        """Check if a user has requested deletion of an item."""
        if content_key in self._deletion_requests:
            return True
        # Check wildcard category deletions
        for req in self._deletion_requests:
            if req.startswith("category:") and req.endswith(":*"):
                category = req.split(":")[1]
                if category in content_key:
                    return True
        return False

    async def get_deletion_requests(self) -> list[str]:
        """Get all pending deletion requests."""
        return list(self._deletion_requests)

    async def clear_deletion_requests(self) -> None:
        """Clear all deletion requests."""
        self._deletion_requests.clear()
        await self._persist()

    # --- Access Logging ---

    def log_access(self, user_id: str, memory_type: str, action: str) -> None:
        """Log a memory access for audit purposes.

        Args:
            user_id: User identifier.
            memory_type: Type of memory accessed.
            action: What was done (read, write, delete).
        """
        if not self._settings.get("log_access", False):
            return

        self._access_log.append({
            "user_id": user_id,
            "memory_type": memory_type,
            "action": action,
            "timestamp": datetime.now().isoformat(),
        })

        # Keep log bounded
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-500:]

    def get_access_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent access log entries."""
        return self._access_log[-limit:]

    # --- Settings ---

    async def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Update privacy settings.

        Args:
            updates: Dict of setting key-value pairs.

        Returns:
            Updated settings.
        """
        self._settings.update(updates)
        await self._persist()
        return self._settings

    async def get_settings(self) -> dict[str, Any]:
        """Get current privacy settings."""
        return dict(self._settings)

    # --- Cleanup ---

    async def get_expired_items(
        self,
        items: list[dict[str, Any]],
    ) -> list[str]:
        """Get IDs of items that have passed their TTL.

        Args:
            items: List of items with 'id', 'privacy_class', and 'created_at' keys.

        Returns:
            List of item IDs to delete.
        """
        now = datetime.now()
        expired = []

        for item in items:
            ttl_days = PrivacyClass(item.get("privacy_class", "public")).default_ttl_days
            if ttl_days is None:
                continue

            created = item.get("created_at")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    continue

            if created and (now - created) > timedelta(days=ttl_days):
                expired.append(item.get("id", ""))

        return expired

    async def get_stats(self) -> dict[str, Any]:
        """Get privacy controls statistics."""
        return {
            "deletion_requests_pending": len(self._deletion_requests),
            "access_log_entries": len(self._access_log),
            "auto_delete_enabled": self._settings.get("auto_delete_enabled", True),
            "encrypt_sensitive_enabled": self._settings.get("encrypt_sensitive", True),
        }

    async def _persist(self) -> None:
        """Persist privacy settings."""
        try:
            privacy_file = settings.get_data_path("memory") / "privacy.json"
            data = {
                "deletion_requests": list(self._deletion_requests),
                "settings": self._settings,
            }
            with open(privacy_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to persist privacy settings: {e}")
