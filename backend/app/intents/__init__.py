"""Intent Recognition & Command Routing.

Processes natural language commands and routes them to
the appropriate tools/actions. Supports Russian and English.

Architecture:
  UserInput → IntentClassifier → IntentRouter → ToolRegistry.execute()
"""
from .processor import IntentProcessor, IntentResult, CommandIntent

__all__ = [
    "IntentProcessor",
    "IntentResult",
    "CommandIntent",
]
