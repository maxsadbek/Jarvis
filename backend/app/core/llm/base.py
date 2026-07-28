"""Abstract base class for LLM providers.

All LLM providers (OpenRouter, Ollama, etc.) must implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional

from backend.app.models.schemas import Message


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Message:
        """Send a chat completion request and get a response.

        Args:
            messages: List of conversation messages.
            system_prompt: Optional system prompt override.
            temperature: Response creativity (0.0 - 2.0).
            max_tokens: Maximum tokens in response.
            model: Specific model override.

        Returns:
            The assistant's response message.
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion response token by token.

        Args:
            messages: List of conversation messages.
            system_prompt: Optional system prompt override.
            temperature: Response creativity (0.0 - 2.0).
            max_tokens: Maximum tokens in response.
            model: Specific model override.

        Yields:
            Text tokens as they are generated.
        """
        yield ""  # pragma: no cover

    @abstractmethod
    async def get_available_models(self) -> list[dict[str, Any]]:
        """Get list of available models from this provider.

        Returns:
            List of model metadata dicts.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is configured and available."""
        ...

    def format_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert internal Message objects to API format."""
        formatted = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, "value") else msg.role
            formatted.append({"role": role, "content": msg.content})
        return formatted
