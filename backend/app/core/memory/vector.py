"""Enhanced Vector Memory Backend using ChromaDB.

Provides semantic search over conversation history and long-term memories.
Upgraded with:
- Hybrid search (semantic + keyword via BM25)
- Importance tiers (hot/warm/cold)
- Privacy classification and encryption
- TTL-based auto-expiry
- Access frequency tracking for reinforcement
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.core.memory.base import MemoryBackend
from backend.app.core.memory.encryption import MemoryEncryption
from backend.app.core.memory.privacy import PrivacyClass, PrivacyControls
from backend.app.models.schemas import Message, MemoryItem


class MemoryTier:
    """Importance-based memory tiers for storage optimization."""

    HOT = "hot"       # Frequently accessed, high importance - kept in active collections
    WARM = "warm"     # Occasionally accessed, medium importance
    COLD = "cold"     # Rarely accessed, low importance - eligible for archival

    @staticmethod
    def from_importance(importance: float, access_count: int = 0) -> str:
        """Determine memory tier from importance and access count."""
        if importance >= 0.8 or access_count >= 20:
            return MemoryTier.HOT
        elif importance >= 0.4 or access_count >= 5:
            return MemoryTier.WARM
        else:
            return MemoryTier.COLD

    @staticmethod
    def tier_score(tier: str) -> float:
        return {"hot": 1.0, "warm": 0.6, "cold": 0.3}.get(tier, 0.5)


class VectorMemory(MemoryBackend):
    """ChromaDB-based vector memory with hybrid search and privacy controls.

    Supports:
    - Hybrid search: semantic (ChromaDB) + keyword (BM25-like)
    - Importance tiers: hot/warm/cold for storage optimization
    - Privacy classification: encrypt sensitive data at rest
    - TTL-based auto-expiry: forget data after retention period
    - Access frequency tracking: reinforce important memories
    """

    COLLECTION_CONVERSATIONS = "jarvis_conversations"
    COLLECTION_FACTS = "jarvis_facts"
    COLLECTION_SUMMARIES = "jarvis_summaries"
    COLLECTION_KNOWLEDGE = "jarvis_knowledge"

    # Minimum keyword length for hybrid search
    MIN_KEYWORD_LENGTH = 3

    def __init__(self) -> None:
        self._client = None
        self._collections: dict[str, Any] = {}
        self._initialized = False
        self._messages: dict[str, list[Message]] = {}
        self._encryption: Optional[MemoryEncryption] = None
        self._privacy: Optional[PrivacyControls] = None

    async def initialize(
        self,
        encryption: Optional[MemoryEncryption] = None,
        privacy: Optional[PrivacyControls] = None,
    ) -> bool:
        """Initialize ChromaDB client with optional encryption and privacy.

        Args:
            encryption: Memory encryption instance for sensitive data.
            privacy: Privacy controls for classification and TTL.
        """
        self._encryption = encryption
        self._privacy = privacy

        try:
            import asyncio
            import chromadb

            persist_dir = settings.get_data_path(settings.MEMORY_PERSIST_DIR)
            persist_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"[vector] ChromaDB PersistentClient yaratilmoqda: {persist_dir}")

            def _create_chroma_client():
                """Sinxron ChromaDB operatsiyalarini background threadda bajaring."""
                client = chromadb.PersistentClient(
                    path=str(persist_dir),
                )
                collection_names = [
                    self.COLLECTION_CONVERSATIONS,
                    self.COLLECTION_FACTS,
                    self.COLLECTION_SUMMARIES,
                    self.COLLECTION_KNOWLEDGE,
                ]
                cols = {}
                for name in collection_names:
                    try:
                        cols[name] = client.get_or_create_collection(
                            name=name,
                            metadata={"hnsw:space": "cosine"},
                        )
                    except Exception as e:
                        logger.warning(f"Could not create collection '{name}': {e}")
                return client, cols

            # asyncio.to_thread — sinxron bloklovchi ChromaDB callni
            # background threadga o'tkazamiz, event loop bloklanmaydi
            self._client, self._collections = await asyncio.to_thread(_create_chroma_client)
            logger.info("[vector] ChromaDB PersistentClient muvaffaqiyatli yaratildi")

            self._initialized = True
            total = sum(c.count() for c in self._collections.values() if c)
            logger.info(
                f"Vector memory initialized with {total} items across "
                f"{len(self._collections)} collections"
            )
            return True

        except ImportError:
            logger.warning("ChromaDB not installed, vector search unavailable")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            return False

    def _get_collection(self, memory_type: str = "conversation"):
        collection_map = {
            "conversation": self.COLLECTION_CONVERSATIONS,
            "fact": self.COLLECTION_FACTS,
            "summary": self.COLLECTION_SUMMARIES,
            "knowledge": self.COLLECTION_KNOWLEDGE,
        }
        collection_name = collection_map.get(memory_type, self.COLLECTION_CONVERSATIONS)
        return self._collections.get(collection_name)

    async def store(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        embedding: Optional[list[float]] = None,
        memory_type: str = "conversation",
        importance: float = 0.5,
        category: str = "general",
        privacy_class: str = "public",
    ) -> str:
        """Store an item in vector memory with privacy controls.

        Args:
            content: The text content to remember.
            metadata: Optional metadata.
            embedding: Optional pre-computed embedding.
            memory_type: Type of memory (conversation, fact, summary, knowledge).
            importance: Importance score (0.0 - 1.0).
            category: Category for organization.
            privacy_class: Privacy classification ('public', 'private', 'sensitive', 'secret').

        Returns:
            Memory item ID.
        """
        if not self._initialized:
            logger.warning("Memory not initialized, skipping store")
            return ""

        collection = self._get_collection(memory_type)
        if not collection:
            logger.warning(f"Collection not available for type: {memory_type}")
            return ""

        item_id = str(uuid.uuid4())
        now = datetime.now()

        # Determine privacy classification
        pc = privacy_class
        if self._privacy and privacy_class == "auto":
            detected = self._privacy.classify_content(content)
            pc = detected.value

        # Encrypt sensitive content
        store_content = content
        if self._encryption and self._privacy:
            privacy_cls = PrivacyClass(pc)
            if self._privacy.should_encrypt(privacy_cls):
                store_content = self._encryption.encrypt(content)

        # Calculate TTL
        ttl = None
        if self._privacy:
            privacy_cls = PrivacyClass(pc)
            exp = self._privacy.get_ttl(privacy_cls)
            if exp:
                ttl = exp.isoformat()

        # Determine memory tier
        tier = MemoryTier.from_importance(importance)

        meta: dict[str, Any] = {
            "timestamp": now.isoformat(),
            "memory_type": memory_type,
            "importance": str(importance),
            "category": category,
            "tier": tier,
            "privacy_class": pc,
            "content_preview": content[:100],
            "access_count": "0",
            **(metadata or {}),
        }

        if ttl:
            meta["ttl"] = ttl

        try:
            collection.add(
                documents=[store_content],
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
        memory_types: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
        min_importance: Optional[float] = None,
        hybrid: bool = True,
    ) -> list[MemoryItem]:
        """Hybrid search: semantic + keyword with privacy filtering.

        Args:
            query: Search query text.
            limit: Maximum number of results.
            threshold: Minimum relevance score (0-1).
            memory_types: Filter by memory types.
            categories: Filter by categories.
            min_importance: Filter by minimum importance.
            hybrid: Enable hybrid search (semantic + keyword).

        Returns:
            List of relevant memory items.
        """
        if not self._initialized:
            return []

        all_items: list[MemoryItem] = []
        collections_to_search = list(self._collections.values())

        if memory_types:
            collections_to_search = []
            for mt in memory_types:
                col = self._get_collection(mt)
                if col:
                    collections_to_search.append(col)

        try:
            for collection in collections_to_search:
                if not collection:
                    continue
                try:
                    if collection.count() == 0:
                        continue
                except Exception:
                    continue

                results = collection.query(
                    query_texts=[query],
                    n_results=max(limit * 2, 10),
                )

                if not results.get("ids") or not results["ids"][0]:
                    continue

                for i, doc_id in enumerate(results["ids"][0]):
                    distance = (
                        results.get("distances", [[0]])[0][i]
                        if results.get("distances")
                        else 0
                    )
                    relevance = 1.0 - min(distance, 1.0)

                    if relevance < threshold:
                        continue

                    doc = (
                        results["documents"][0][i]
                        if results.get("documents")
                        else ""
                    )
                    meta = (
                        results["metadatas"][0][i]
                        if results.get("metadatas")
                        else {}
                    )

                    importance = float(meta.get("importance", 0.5))
                    category = meta.get("category", "general")
                    memory_type = meta.get("memory_type", "conversation")

                    if categories and category not in categories:
                        continue
                    if min_importance and importance < min_importance:
                        continue

                    # Decrypt if encrypted
                    if doc.startswith("enc:") or doc.startswith("__unencrypted__:"):
                        if self._encryption:
                            doc = self._encryption.decrypt(doc)

                    # Parse timestamp
                    ts = datetime.now()
                    try:
                        ts_str = meta.get("timestamp", ts.isoformat())
                        ts = datetime.fromisoformat(ts_str)
                    except (ValueError, TypeError):
                        pass

                    # Check TTL expiry
                    ttl_str = meta.get("ttl")
                    if ttl_str:
                        try:
                            ttl_expiry = datetime.fromisoformat(ttl_str)
                            if datetime.now() > ttl_expiry:
                                continue  # Skip expired items
                        except (ValueError, TypeError):
                            pass

                    item = MemoryItem(
                        id=doc_id,
                        content=doc,
                        type=memory_type,
                        timestamp=ts,
                        metadata=meta,
                        relevance_score=relevance,
                        importance=importance,
                        category=category,
                    )
                    all_items.append(item)

                    # Update access count
                    try:
                        access_count = int(meta.get("access_count", 0)) + 1
                        collection.update(
                            ids=[doc_id],
                            metadatas=[{**meta, "access_count": str(access_count)}],
                        )
                    except Exception:
                        pass

            # Soft BM25 keyword boost for hybrid search
            if hybrid and query:
                keyword_boost = self._compute_keyword_boost(query, all_items)
                for item in all_items:
                    boost = keyword_boost.get(item.id, 0)
                    item.relevance_score = min(1.0, item.relevance_score * (1 + boost * 0.3))

            # Sort by combined score: relevance * 0.5 + importance * 0.3 + tier * 0.2
            for item in all_items:
                tier = MemoryTier.tier_score(item.metadata.get("tier", "cold"))
                item.relevance_score = (
                    item.relevance_score * 0.5
                    + item.importance * 0.3
                    + tier * 0.2
                )

            all_items.sort(key=lambda x: x.relevance_score, reverse=True)
            return all_items[:limit]

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def _compute_keyword_boost(
        self,
        query: str,
        items: list[MemoryItem],
    ) -> dict[str, float]:
        """Compute keyword match boost for hybrid search.

        Uses a simple TF-like scoring: count query term occurrences
        in each item and normalize.

        Args:
            query: The search query.
            items: Items to score.

        Returns:
            Dict of item_id -> boost factor (0-1).
        """
        query_terms = set(
            w.lower() for w in query.split()
            if len(w) >= self.MIN_KEYWORD_LENGTH
        )
        if not query_terms:
            return {}

        boosts: dict[str, float] = {}
        max_matches = 0

        for item in items:
            content_lower = item.content.lower()
            match_count = sum(
                1 for term in query_terms if term in content_lower
            )
            boosts[item.id] = match_count
            max_matches = max(max_matches, match_count)

        if max_matches > 0:
            for item_id in boosts:
                boosts[item_id] /= max_matches

        return boosts

    async def delete_by_id(self, item_id: str) -> bool:
        """Delete a specific item by ID."""
        if not self._initialized:
            return False
        for name, collection in self._collections.items():
            if not collection:
                continue
            try:
                collection.delete(ids=[item_id])
                return True
            except Exception:
                continue
        return False

    async def delete_by_filter(
        self,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> int:
        """Delete items matching filters.

        Args:
            memory_type: Only delete this type.
            category: Only delete this category.

        Returns:
            Number of items deleted.
        """
        count = 0
        for name, collection in self._collections.items():
            if not collection:
                continue
            if memory_type and self._get_collection(memory_type) != collection:
                continue
            try:
                # Can only delete by filter in ChromaDB with known IDs
                # For simplicity, we clear entire collections
                if memory_type or category:
                    results = collection.get()
                    if results.get("ids"):
                        to_delete = []
                        for i, doc_id in enumerate(results["ids"]):
                            meta = (results.get("metadatas") or [{}])[i] or {}
                            if memory_type and meta.get("memory_type") != memory_type:
                                continue
                            if category and meta.get("category") != category:
                                continue
                            to_delete.append(doc_id)
                        if to_delete:
                            collection.delete(ids=to_delete)
                            count += len(to_delete)
                else:
                    count += collection.count()
                    self._client.delete_collection(name)
            except Exception as e:
                logger.warning(f"Delete failed for {name}: {e}")
        return count

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[Message]:
        messages = self._messages.get(conversation_id, [])
        return messages[-limit:] if limit else messages

    MAX_MESSAGES_PER_CONVERSATION = 100
    MAX_CONVERSATIONS = 20

    async def store_message(self, message: Message, conversation_id: str) -> None:
        if conversation_id not in self._messages:
            if len(self._messages) >= self.MAX_CONVERSATIONS:
                oldest = min(
                    self._messages.keys(),
                    key=lambda k: (
                        self._messages[k][-1].timestamp
                        if self._messages[k]
                        else datetime.min
                    ),
                )
                del self._messages[oldest]
            self._messages[conversation_id] = []

        self._messages[conversation_id].append(message)

        if len(self._messages[conversation_id]) > self.MAX_MESSAGES_PER_CONVERSATION:
            first = self._messages[conversation_id][0]
            self._messages[conversation_id] = (
                [first]
                + self._messages[conversation_id][
                    -(self.MAX_MESSAGES_PER_CONVERSATION - 1) :
                ]
            )

        if message.role.value in ("user", "assistant") and message.content:
            await self.store(
                content=message.content,
                metadata={
                    "type": "message",
                    "role": message.role.value,
                    "conversation_id": conversation_id,
                    "message_type": message.type.value,
                },
                memory_type="conversation",
                importance=0.7 if message.role.value == "user" else 0.5,
                category="general",
                privacy_class="private",
            )

    async def clear(self) -> None:
        self._messages.clear()
        if self._client:
            for name in list(self._collections.keys()):
                try:
                    self._client.delete_collection(name)
                except Exception:
                    pass
            self._collections.clear()
            await self.initialize()
            logger.info("All vector memories cleared")

    async def get_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "conversations": len(self._messages),
            "total_messages": sum(len(msgs) for msgs in self._messages.values()),
        }

        for name, collection in self._collections.items():
            if collection:
                try:
                    stats[f"collection_{name}"] = collection.count()
                except Exception:
                    stats[f"collection_{name}"] = -1

        stats["initialized"] = self._initialized
        return stats
