# Advanced Memory System - Upgraded
# Provides permanent user profile, privacy controls, encryption, hybrid search

from .base import MemoryBackend
from .vector import VectorMemory, MemoryTier
from .short_term import ShortTermMemory, ShortTermMemoryConfig, ConversationBuffer
from .preferences import UserPreferences, UserPreference
from .facts import FactsMemory, ImportantFact
from .habits import HabitsMemory, UserHabit
from .summarizer import ConversationSummarizer, ConversationSummary
from .retrieval import MemoryRetrieval, MemoryQuery, MemorySearchResult
from .manager import MemoryManager
from .user_profile import UserProfile, UserProject
from .privacy import PrivacyControls, PrivacyClass
from .encryption import MemoryEncryption

__all__ = [
    # Base
    "MemoryBackend",
    # Vector
    "VectorMemory",
    "MemoryTier",
    # Short-term
    "ShortTermMemory",
    "ShortTermMemoryConfig",
    "ConversationBuffer",
    # Preferences
    "UserPreferences",
    "UserPreference",
    # Facts
    "FactsMemory",
    "ImportantFact",
    # Habits
    "HabitsMemory",
    "UserHabit",
    # Summarizer
    "ConversationSummarizer",
    "ConversationSummary",
    # Retrieval
    "MemoryRetrieval",
    "MemoryQuery",
    "MemorySearchResult",
    # Manager
    "MemoryManager",
    # New - Profile
    "UserProfile",
    "UserProject",
    # New - Privacy
    "PrivacyControls",
    "PrivacyClass",
    # New - Encryption
    "MemoryEncryption",
]
