"""Vector Memory Backend using ChromaDB.

Provides semantic search over conversation history and long-term memories.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.core.memory.base import MemoryBackend
from backend.app.models.schemas import Message, MemoryItem


class VectorMemory(MemoryBackend):
    """ChromaDB-based vector memory with semantic search."""

    def __init__(self) -> None:
        self._collection = None
        self._client = None
        self._initialized = False
        self._messages: dict[str, list[Message]] = {}  # conversation_id -> messages

    async def initialize(self) -> bool:
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            persist_dir = settings.get_data_path(settings.MEMORY_PERSIST_DIR)

            self._client = chromadb.Client(
                ChromaSettings(
                    persist_directory=str(persist_dir),
                    anonymized_telemetry=False,
                )
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=settings.MEMORY_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )

            self._initialized = True
            count = self._collection.count()
            logger.info(f"Vector memory initialized with {count} existing items")
            return True

        except ImportError:
            logger.warning("ChromaDB not installed, falling back to JSON memory")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            return False

    async def store(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        embedding: Optional[list[float]] = None,
    ) -> str:
        """Store an item in vector memory."""
        if not self._initialized or not self._collection:
            logger.warning("Memory not initialized, skipping store")
            return ""

        item_id = str(uuid.uuid4())
        meta = {
            "timestamp": datetime.now().isoformat(),
            "content_preview": content[:200],
            **(metadata or {}),
        }

        try:
            self._collection.add(
                documents=[content],
                metadatas=[meta],
                ids=[item_id],
            )
            return item_id
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return ""

    async def search(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.5,
    ) -> list[MemoryItem]:
        """Search for relevant memories."""
        if not self._initialized or not self._collection:
            return []

        try:
            actual_limit = max(limit, 1)
            results = self._collection.query(
                query_texts=[query],
                n_results=actual_limit,
            )

            items = []
            if results.get("ids") and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    distance = results.get("distances", [[0]])[0][i] if results.get("distances") else 0
                    relevance = 1.0 - min(distance, 1.0)

                    if relevance < threshold:
                        continue

                    doc = results["documents"][0][i] if results.get("documents") else ""
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}

                    items.append(MemoryItem(
                        id=doc_id,
                        content=doc,
                        type=meta.get("type", "conversation"),
                        timestamp=datetime.fromisoformat(meta.get("timestamp", datetime.now().isoformat())),
                        metadata=meta,
                        relevance_score=relevance,
                    ))

            return items
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """Get messages from a conversation."""
        messages = self._messages.get(conversation_id, [])
        return messages[-limit:] if limit else messages

    async def store_message(self, message: Message, conversation_id: str) -> None:
        """Store a message in memory."""
        if conversation_id not in self._messages:
            self._messages[conversation_id] = []
        self._messages[conversation_id].append(message)

        # Also store in vector DB for semantic search
        if message.role.value in ("user", "assistant") and message.content:
            await self.store(
                content=message.content,
                metadata={
                    "type": "message",
                    "role": message.role.value,
                    "conversation_id": conversation_id,
                    "message_type": message.type.value,
                },
            )

    async def clear(self) -> None:
        """Clear all memories."""
        self._messages.clear()
        if self._collection:
            try:
                self._client.delete_collection(settings.MEMORY_COLLECTION)
                self._collection = self._client.create_collection(
                    settings.MEMORY_COLLECTION
                )
                logger.info("Memory cleared")
            except Exception as e:
                logger.error(f"Failed to clear memory: {e}")

    async def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        stats = {
            "conversations": len(self._messages),
            "total_messages": sum(len(msgs) for msgs in self._messages.values()),
            "vector_items": self._collection.count() if self._collection else 0,
            "initialized": self._initialized,
        }
        return stats
