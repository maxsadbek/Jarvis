"""OpenRouter LLM Provider.

Integrates with OpenRouter API for access to 300+ models
including GPT-4, Claude, Gemini, Llama, and more.
"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger

from backend.app.config import settings
from backend.app.core.llm.base import LLMProvider
from backend.app.models.schemas import Message, MessageRole, MessageType


class OpenRouterProvider(LLMProvider):
    """LLM provider using OpenRouter API gateway."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._available = False

    async def initialize(self) -> None:
        """Initialize the HTTP client and check availability."""
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OpenRouter API key not configured")
            self._available = False
            return

        self._client = httpx.AsyncClient(
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        # Verify connectivity
        try:
            response = await self._client.get("/models")
            self._available = response.status_code == 200
            if self._available:
                logger.info("OpenRouter provider initialized successfully")
            else:
                logger.warning(
                    f"OpenRouter connectivity check failed: {response.status_code}"
                )
        except Exception as e:
            logger.error(f"OpenRouter initialization failed: {e}")
            self._available = False

    @property
    def provider_name(self) -> str:
        return "OpenRouter"

    @property
    def is_available(self) -> bool:
        return self._available and settings.OPENROUTER_API_KEY is not None

    def _build_system_prompt(self) -> str:
        """Build the JARVIS system prompt."""
        return (
            "You are JARVIS, an advanced AI personal assistant inspired by "
            "Tony Stark's JARVIS. You are helpful, intelligent, efficient, "
            "and have a slightly sophisticated personality.\n\n"
            "Your capabilities include:\n"
            "- Natural conversation with memory of past interactions\n"
            "- Voice-controlled operation\n"
            "- Web searching and research\n"
            "- File management and code assistance\n"
            "- System control and automation\n"
            "- Task planning and execution\n\n"
            "Guidelines:\n"
            "- Be concise but thorough when needed\n"
            "- Use a professional yet warm tone\n"
            "- When asked to do tasks, explain your approach\n"
            "- If something is unclear, ask clarifying questions\n"
            "- You can use tools to execute tasks when appropriate\n"
            "- Always prioritize safety and user privacy\n\n"
            "Current date and time information is available if needed."
        )

    async def chat(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Message:
        """Send a chat completion via OpenRouter."""
        if not self.is_available:
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content="I'm sorry, but my AI brain isn't connected right now. "
                "Please check your OpenRouter API key configuration.",
            )

        formatted_messages = self.format_messages(messages)

        request_body = {
            "model": model or settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt or self._build_system_prompt()},
                *formatted_messages,
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        # Add OpenRouter-specific headers
        headers = {}
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_SITE_NAME:
            headers["X-Title"] = settings.OPENROUTER_SITE_NAME

        # Configure model fallback
        if settings.OPENROUTER_FALLBACK_MODEL:
            request_body["models"] = [settings.OPENROUTER_FALLBACK_MODEL]

        start_time = time.time()

        try:
            response = await self._client.post(
                "/chat/completions",
                json=request_body,
                headers=headers if headers else None,
            )
            response.raise_for_status()
            data = response.json()

            elapsed = (time.time() - start_time) * 1000
            content = data["choices"][0]["message"]["content"]
            model_used = data.get("model", model or settings.OPENROUTER_MODEL)

            logger.info(f"OpenRouter response in {elapsed:.0f}ms using {model_used}")

            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.TEXT,
                content=content,
                metadata={
                    "model": model_used,
                    "tokens": data.get("usage", {}),
                    "processing_time_ms": elapsed,
                },
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {e.response.text}")
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content=f"I encountered an error communicating with the AI service. "
                f"Status: {e.response.status_code}",
            )
        except httpx.TimeoutException:
            logger.error("OpenRouter request timed out")
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content="The AI service timed out. Please try again.",
            )
        except Exception as e:
            logger.error(f"OpenRouter request failed: {e}")
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content=f"I'm sorry, something went wrong: {str(e)}",
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
        """Stream a chat completion via OpenRouter SSE."""
        if not self.is_available:
            yield "I'm sorry, but my AI brain isn't connected right now."
            return

        formatted_messages = self.format_messages(messages)

        request_body = {
            "model": model or settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                *formatted_messages,
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }

        headers = {}
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_SITE_NAME:
            headers["X-Title"] = settings.OPENROUTER_SITE_NAME

        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                json=request_body,
                headers=headers if headers else None,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            import json
                            data = json.loads(data_str)
                            if content := data.get("choices", [{}])[0].get("delta", {}).get("content"):
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"OpenRouter streaming failed: {e}")
            yield f"\n\n[Error: {str(e)}]"

    async def get_available_models(self) -> list[dict[str, Any]]:
        """Fetch available models from OpenRouter."""
        if not self._client:
            return []

        try:
            response = await self._client.get("/models")
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter models: {e}")
            return []

    async def close(self) -> None:
        """Clean up the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
