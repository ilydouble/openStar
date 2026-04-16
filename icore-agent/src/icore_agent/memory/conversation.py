"""Conversation memory backed by Redis.

Each conversation is keyed by session_id.  Messages are stored as a
JSON list and expire after settings.memory_ttl_seconds.
"""

from __future__ import annotations

import json
import structlog
import redis.asyncio as aioredis
from typing import Any

from ..config import settings

log = structlog.get_logger()

_Message = dict[str, Any]


class ConversationMemory:
    """Async Redis-backed conversation history store."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"icore:conv:{session_id}"

    async def get_messages(self, session_id: str) -> list[_Message]:
        """Return all messages for a session (empty list if not found)."""
        client = await self._get_client()
        raw = await client.get(self._key(session_id))
        if raw is None:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("conversation_memory_decode_error", session_id=session_id)
            return []

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """Append a single message and refresh TTL."""
        messages = await self.get_messages(session_id)
        messages.append({"role": role, "content": content})
        client = await self._get_client()
        await client.set(
            self._key(session_id),
            json.dumps(messages, ensure_ascii=False),
            ex=settings.memory_ttl_seconds,
        )
        log.debug("conversation_memory_append", session_id=session_id, role=role,
                  total_messages=len(messages))

    async def clear(self, session_id: str) -> None:
        """Delete all messages for a session."""
        client = await self._get_client()
        await client.delete(self._key(session_id))
        log.info("conversation_memory_cleared", session_id=session_id)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None


# App-level singleton — import from here
memory = ConversationMemory()
