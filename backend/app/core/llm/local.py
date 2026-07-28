"""Local LLM Provider using Ollama.

Provides integration with locally running LLM models via Ollama.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger

from backend.app.config import settings
from backend.app.core.llm.base import LLMProvider
from backend.app.models.schemas import Message, MessageRole, MessageType


class LocalLLMProvider(LLMProvider):
    """LLM provider using local Ollama models."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._available = False

    async def initialize(self) -> None:
        """Initialize client and check Ollama availability."""
        self._client = httpx.AsyncClient(
            base_url=settings.OLLAMA_BASE_URL,
            timeout=httpx.Timeout(120.0, connect=5.0),
        )

        try:
            response = await self._client.get("/api/tags")
            self._available = response.status_code == 200
            if self._available:
                models = response.json().get("models", [])
                logger.info(f"Ollama available with {len(models)} models")
            else:
                logger.warning("Ollama not available")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._available = False

    @property
    def provider_name(self) -> str:
        return "Ollama (Local)"

    @property
    def is_available(self) -> bool:
        return self._available and settings.USE_LOCAL_LLM

    async def chat(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Message:
        """Send a chat completion to local Ollama."""
        if not self.is_available:
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content="Local AI model is not available. Please start Ollama or check configuration.",
            )

        formatted = self.format_messages(messages)

        # Build prompt with system message
        full_content = ""
        if system_prompt:
            full_content = f"<system>{system_prompt}</system>\n\n"

        for msg in formatted:
            role = msg["role"].upper() if msg["role"] != "assistant" else "ASSISTANT"
            full_content += f"<{role}>{msg['content']}</{role}>\n"

        request_body = {
            "model": model or settings.OLLAMA_MODEL,
            "prompt": full_content.strip(),
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            response = await self._client.post("/api/generate", json=request_body)
            response.raise_for_status()
            data = response.json()

            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.TEXT,
                content=data.get("response", ""),
                metadata={"model": model or settings.OLLAMA_MODEL},
            )
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content=f"Local AI error: {str(e)}",
            )

    async def chat_stream(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a response from local Ollama."""
        if not self.is_available:
            yield "Local AI model is not available."
            return

        formatted = self.format_messages(messages)

        full_content = ""
        if system_prompt:
            full_content = f"<system>{system_prompt}</system>\n\n"
        for msg in formatted:
            role = msg["role"].upper()
            full_content += f"<{role}>{msg['content']}</{role}>\n"

        request_body = {
            "model": model or settings.OLLAMA_MODEL,
            "prompt": full_content.strip(),
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with self._client.stream(
                "POST", "/api/generate", json=request_body
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        import json
                        data = json.loads(line)
                        if token := data.get("response"):
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")

    async def get_available_models(self) -> list[dict[str, Any]]:
        """Get available Ollama models."""
        if not self._client:
            return []
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            return response.json().get("models", [])
        except Exception as e:
            logger.error(f"Failed to get Ollama models: {e}")
            return []

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
