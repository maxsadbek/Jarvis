"""AI Engine - The Brain of JARVIS.

Orchestrates all AI operations:
- Routes requests to the appropriate LLM provider
- Manages conversation context and memory via MemoryManager
- Coordinates tool execution
- Handles voice transcription and synthesis
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, AsyncGenerator, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.core.llm.base import LLMProvider
from backend.app.core.llm.openrouter import OpenRouterProvider
from backend.app.core.llm.local import LocalLLMProvider
from backend.app.core.memory.manager import MemoryManager
from backend.app.core.memory.context import ContextManager
from backend.app.models.schemas import (
    ConnectionState,
    Message,
    MessageRole,
    MessageType,
    SystemStatus,
)
from backend.app.tools.base import ToolRegistry
from backend.app.tools.automation import AutomationEngine
from backend.app.intents import IntentProcessor, CommandIntent
from backend.app.plugins import PluginRegistry


class AIEngine:
    """Core AI engine orchestrating LLM, memory, and tools."""

    def __init__(self) -> None:
        self._llm_provider: Optional[LLMProvider] = None
        self._memory: Optional[MemoryManager] = None
        self._memory_ready: bool = False
        self._context_manager: Optional[ContextManager] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._automation: Optional[AutomationEngine] = None
        self._intent_processor: Optional[IntentProcessor] = None
        self._plugin_registry: Optional[PluginRegistry] = None
        self._vision_controller: Optional[Any] = None  # lazy - hand control
        self._start_time: float = time.time()
        self._state: ConnectionState = ConnectionState.DISCONNECTED

    async def initialize(self) -> None:
        """Initialize all engine components."""
        logger.info("Initializing JARVIS AI Engine...")

        # 1. Initialize LLM provider
        if settings.OPENROUTER_API_KEY:
            logger.info("Connecting to OpenRouter...")
            self._llm_provider = OpenRouterProvider()
            await self._llm_provider.initialize()
            if self._llm_provider.is_available:
                logger.info(f"Connected to {self._llm_provider.provider_name}")

        # Fallback to local LLM
        if (not self._llm_provider or not self._llm_provider.is_available) and settings.USE_LOCAL_LLM:
            logger.info("Trying local Ollama...")
            self._llm_provider = LocalLLMProvider()
            await self._llm_provider.initialize()
            if self._llm_provider.is_available:
                logger.info(f"Connected to {self._llm_provider.provider_name}")

        if not self._llm_provider or not self._llm_provider.is_available:
            logger.warning("No LLM provider available")

        # 2. Initialize advanced memory system
        if settings.MEMORY_ENABLED:
            logger.info("Initializing memory system...")
            self._memory = MemoryManager()
            memory_ok = await self._memory.initialize(llm_provider=self._llm_provider)
            if memory_ok:
                self._memory_ready = True
                logger.info("Memory system ready")
            else:
                self._memory_ready = False
                logger.warning("Memory system initialized with degraded functionality")
        else:
            self._memory_ready = False

        # 3. Initialize context manager (uses MemoryManager)
        self._context_manager = ContextManager(self._memory)
        logger.info("Context manager ready")

        # 4. Initialize tool registry
        if settings.TOOLS_ENABLED:
            self._tool_registry = ToolRegistry()
            await self._tool_registry.initialize()
            logger.info(f"Tool registry ready with {len(self._tool_registry.tools)} tools")

            # 5. Initialize automation engine if tools are enabled
            if settings.AUTOMATION_ENABLED:
                self._automation = AutomationEngine(tool_registry=self._tool_registry)
                await self._automation.initialize()
                logger.info("Automation engine ready")

        # 6. Initialize intent processor (natural language command router)
        self._intent_processor = IntentProcessor(llm_provider=self._llm_provider)
        logger.info("Intent processor ready")

        # 6.5. Vision control (hand gestures) - optional, lazy import so the
        # backend still runs without OpenCV/MediaPipe installed.
        try:
            from config.vision import load_vision_config
            if load_vision_config().enabled_on_startup:
                from vision.vision_control import VisionController
                self._vision_controller = VisionController.from_config()
                await asyncio.to_thread(self._vision_controller.start)
                logger.info("Vision control started (enabled_on_startup)")
        except ImportError:
            logger.debug("Vision control unavailable (install opencv-python + mediapipe)")
        except Exception as e:
            logger.warning(f"Vision control failed to start: {e}")

        # 7. Initialize plugin system
        self._plugin_registry = PluginRegistry()
        plugin_count = await self._plugin_registry.discover_and_load()
        logger.info(f"Plugin registry ready: {plugin_count} plugins")

        logger.info("JARVIS AI Engine initialization complete")

    @property
    def state(self) -> ConnectionState:
        return self._state

    @state.setter
    def state(self, new_state: ConnectionState) -> None:
        self._state = new_state

    @property
    def is_llm_ready(self) -> bool:
        return self._llm_provider is not None and self._llm_provider.is_available

    @property
    def memory(self) -> Optional[MemoryManager]:
        """Get the memory manager (only if successfully initialized)."""
        return self._memory if self._memory_ready else None

    async def chat(
        self,
        message: str,
        conversation_id: str,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> Message | AsyncGenerator[str, None]:
        """Process a chat message and return AI response.

        Uses the MemoryManager for personalized context and
        automatic memory storage. Runs intent detection first
        for fast command routing without LLM.

        Args:
            message: The user's message.
            conversation_id: The conversation ID.
            stream: Whether to stream the response.
            model: Optional model override.

        Returns:
            Either a Message or an async generator for streaming.
        """
        if not self.is_llm_ready:
            return Message(
                role=MessageRole.ASSISTANT,
                type=MessageType.ERROR,
                content="JARVIS AI engine is not initialized. Please check configuration and try again.",
                metadata={"conversation_id": conversation_id},
            )

        self.state = ConnectionState.PROCESSING

        # ── Stage 1: Intent Detection (fast path) ──
        if self._intent_processor:
            intent = await self._intent_processor.process(message)

            if intent.intent != CommandIntent.CHAT and intent.intent != CommandIntent.UNKNOWN:
                # Handle via tool directly
                result = await self._execute_intent(intent, conversation_id)
                self.state = ConnectionState.CONNECTED
                return Message(
                    role=MessageRole.ASSISTANT,
                    type=MessageType.TEXT,
                    content=result,
                    metadata={
                        "conversation_id": conversation_id,
                        "intent": intent.intent.value,
                        "tool": intent.tool_name,
                    },
                )

        # ── Stage 2: Build context using MemoryManager ──
        context_messages = await self._context_manager.build_context(
            conversation_id=conversation_id,
            current_message=message,
        )

        # Store user message via MemoryManager (processes through all subsystems)
        user_msg = Message(
            role=MessageRole.USER,
            content=message,
            metadata={"conversation_id": conversation_id},
        )
        mem = self.memory
        if mem:
            await mem.process_message(user_msg, conversation_id)

        if stream:
            return self._stream_response(context_messages, conversation_id, model)
        else:
            # Get full response
            response = await self._llm_provider.chat(
                messages=context_messages,
                model=model,
            )
            response.metadata["conversation_id"] = conversation_id

            # Store assistant response via MemoryManager
            if mem:
                await mem.process_message(response, conversation_id)

            self.state = ConnectionState.CONNECTED
            return response

    async def _stream_response(
        self,
        messages: list[Message],
        conversation_id: str,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response token by token."""
        full_response = ""
        try:
            async for token in self._llm_provider.chat_stream(
                messages=messages,
                model=model,
            ):
                full_response += token
                yield token
        finally:
            # Store the complete response
            mem = self.memory
            if mem and full_response:
                response_msg = Message(
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    metadata={"conversation_id": conversation_id},
                )
                await mem.process_message(response_msg, conversation_id)
            self.state = ConnectionState.CONNECTED

    async def get_status(self) -> SystemStatus:
        """Get the current system status."""
        import psutil

        memory_stats = {}
        mem = self.memory
        if mem:
            try:
                memory_stats = await mem.get_stats()
            except Exception:
                pass

        return SystemStatus(
            llm_connected=self.is_llm_ready,
            llm_model=settings.OPENROUTER_MODEL if self.is_llm_ready else None,
            stt_ready=True,
            tts_ready=True,
            memory_ready=self._memory_ready,
            tools_loaded=list(self._tool_registry.tools.keys()) if self._tool_registry else [],
            cpu_usage=psutil.cpu_percent(interval=0.1),
            memory_usage=psutil.virtual_memory().percent,
            uptime_seconds=time.time() - self._start_time,
        )

    async def get_memory_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        mem = self.memory
        if mem:
            return await mem.get_stats()
        return {"error": "Memory not available"}

    async def clear_memory(self) -> bool:
        """Clear all memories."""
        mem = self.memory
        if mem:
            await mem.clear()
            return True
        return False

    async def search_memories(self, query: str, limit: int = 5) -> list[Any]:
        """Search stored memories."""
        mem = self.memory
        if mem:
            return await mem.search(query=query, limit=limit)
        return []

    async def _execute_intent(self, intent: IntentResult, conversation_id: str) -> str:
        """Execute a command intent via the tool system.

        Args:
            intent: Parsed intent with tool, action, params.
            conversation_id: Current conversation.

        Returns:
            Human-readable result string.
        """
        logger.info(f"Executing intent: {intent.intent.value} → {intent.tool_name}.{intent.action}")

        # ── Redirect: system_ctl open_app/open_website → app_control (backward compat) ──
        if intent.tool_name == "system_ctl" and intent.action in ("open_app", "open_website", "open_url"):
            intent.tool_name = "app_control"
            intent.action = "open_url" if intent.action == "open_website" else "open"
            logger.info(f"  Redirected to {intent.tool_name}.{intent.action}")

        # ── Handle memory intents directly (not through tool registry) ──
        if intent.tool_name == "memory":
            return await self._handle_memory_intent(intent)

        # ── Handle vision control intents directly ──
        if intent.tool_name == "vision":
            return await self._handle_vision_intent(intent)

        # ── Handle new control modules directly (not in ToolRegistry) ──
        direct_tools = {
            "app_control": ("backend.app.tools.control.app_control", "AppControlTool"),
            "system_control": ("backend.app.tools.control.system_control", "SystemControlTool"),
            "system": ("backend.app.tools.control.system_control", "SystemControlTool"),
            "media_control": ("backend.app.tools.control.media_control", "MediaControlTool"),
            "file_control": ("backend.app.tools.control.file_control", "FileControlTool"),
            "developer": ("backend.app.tools.control.developer_mode", "DeveloperModeTool"),
        }

        if intent.tool_name in direct_tools:
            import importlib
            module_path, class_name = direct_tools[intent.tool_name]
            try:
                module = importlib.import_module(module_path)
                tool_cls = getattr(module, class_name)
                tool = tool_cls()
                result = await tool.execute(**{**intent.params, "action": intent.action})
                if result.get("success"):
                    return result.get("result", "Done!")
                return result.get("error", "Command failed")
            except Exception as e:
                logger.error(f"Direct tool execution failed: {e}")
                return f"Command failed: {str(e)}"

        # ── Handle via existing ToolRegistry (system_ctl, browser, web_search, etc.) ──
        if self._tool_registry:
            from backend.app.models.schemas import ToolCall, ToolName

            tool_name_map = {
                "system_ctl": ToolName.SYSTEM_CTL,
                "browser": ToolName.BROWSER,
                "web_search": ToolName.WEB_SEARCH,
                "file_ops": ToolName.FILE_OPS,
                "command_runner": ToolName.COMMAND_RUNNER,
                "code_exec": ToolName.CODE_EXEC,
            }

            tn = tool_name_map.get(intent.tool_name, ToolName.WEB_SEARCH)
            tc = ToolCall(
                id=uuid.uuid4().hex,
                name=tn,
                arguments={**intent.params, "action": intent.action},
            )
            result = await self._tool_registry.execute_tool(tool_call=tc, auto_confirm=True)

            if result.status == "completed":
                return result.result or "Done!"
            elif result.status == "denied":
                return f"I can't do that: {result.error}"
            elif result.status == "error":
                return f"Command failed: {result.error}"

        return "Tool system not available."

    async def _handle_memory_intent(self, intent: IntentResult) -> str:
        """Handle memory-related intents directly."""
        mem = self.memory
        if not mem:
            return "Memory system not available."

        if intent.action == "save_name":
            if "=" in intent.params.get("content", ""):
                name = intent.params["content"].split("=")[1].strip()
                profile = await mem.get_profile()
                await profile.set_field("name", name)
                return f"Запомнил! Ваше имя {name}."
            return "Запомнил!"

        if intent.action == "save":
            await mem.add_fact(
                fact_text=intent.params.get("content", ""),
                category="general",
            )
            return "Saved to memory."

        if intent.action == "recall":
            facts = await mem.get_facts(limit=5)
            if facts:
                return "Important things I remember: " + "; ".join(f.fact for f in facts)
            return "I don't have any saved memories yet."

        return "Processing memory request..."

    async def _handle_vision_intent(self, intent: IntentResult) -> str:
        """Toggle the hand-controlled vision pipeline on/off.

        The VisionController is created lazily from ``config/vision.yaml`` on
        the first enable, so the backend works normally until hand control is
        actually requested.
        """
        state = intent.params.get("state", "on")

        if self._vision_controller is None:
            try:
                from vision.vision_control import VisionController
                self._vision_controller = VisionController.from_config()
            except Exception as e:
                logger.warning("Vision control unavailable: %s", e)
                return "Qo'l bilan boshqarish mavjud emas (opencv-python va mediapipe o'rnatilganini tekshiring)."

        # start()/stop() open the camera and join the vision thread - run them
        # off the event loop so a busy camera never blocks the backend.
        if state == "on":
            try:
                started = await asyncio.to_thread(self._vision_controller.start)
            except Exception as e:
                logger.warning("Vision control failed to start: %s", e)
                self._vision_controller = None  # allow a clean retry
                return f"Qo'l bilan boshqarishni yoqib bo'lmadi: {e}"
            return (
                "Qo'l bilan boshqarish yoqildi."
                if started
                else "Qo'l bilan boshqarish allaqachon yoqilgan."
            )

        await asyncio.to_thread(self._vision_controller.stop)
        return "Qo'l bilan boshqarish o'chirildi."

    async def shutdown(self) -> None:
        """Gracefully shut down the engine."""
        logger.info("Shutting down JARVIS engine...")
        if self._vision_controller is not None:
            await asyncio.to_thread(self._vision_controller.stop)
            self._vision_controller = None
        if hasattr(self._llm_provider, "close"):
            await self._llm_provider.close()
        mem = self.memory
        if mem:
            await mem.shutdown()
        if self._plugin_registry:
            await self._plugin_registry.shutdown_all()
        self.state = ConnectionState.DISCONNECTED
        logger.info("JARVIS engine shutdown complete")
