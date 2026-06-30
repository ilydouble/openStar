"""Redis read-through cache for durable user-memory lookups.

build_memory_prompt() runs on EVERY chat turn and previously hit Postgres
twice per turn (get_or_create_profile + list_active_facts) even though those
rows only change when a session-end extraction (or an account-memory edit)
writes to them — i.e. far less often than they're read. Caching the raw
profile+facts payload (not the final ranked prompt!) removes that DB
round-trip from the hot path while still letting rank_facts_for_turn() score
facts freshly against each turn's actual message — so personalization quality
is unaffected, only the storage I/O is.

Cache entries are short-lived (memory_read_cache_ttl_seconds) AND explicitly
invalidated wherever UserMemoryService writes a profile or fact, so staleness
is bounded on both ends.
"""

from __future__ import annotations

import json
from typing import Any

import redis

from icore_agent.config import settings
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)


class MemoryReadCache:
    """Sync Redis cache for one user's profile + active-fact snapshot."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    def _key(self, user_id: str) -> str:
        return f"icore:user_memory:snapshot:{user_id}"

    def get_snapshot(self, user_id: str) -> dict[str, Any] | None:
        """Return a cached {"profile": ..., "facts": [...]}  payload, if any."""
        try:
            raw = self._get_client().get(self._key(user_id))
        except redis.RedisError as exc:
            log.warning("user_memory_cache_unavailable",
                        operation="get", error=str(exc))
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            log.warning("user_memory_cache_decode_error", user_id=user_id)
            return None

    def set_snapshot(self, user_id: str, payload: dict[str, Any]) -> None:
        """Cache one user's profile + active-fact snapshot briefly."""
        try:
            self._get_client().set(
                self._key(user_id),
                json.dumps(payload, ensure_ascii=False),
                ex=settings.memory_read_cache_ttl_seconds,
            )
        except redis.RedisError as exc:
            log.warning("user_memory_cache_unavailable",
                        operation="set", error=str(exc))

    def invalidate(self, user_id: str) -> None:
        """Drop the cached snapshot so the next turn re-reads from Postgres."""
        try:
            self._get_client().delete(self._key(user_id))
        except redis.RedisError as exc:
            log.warning("user_memory_cache_unavailable",
                        operation="invalidate", error=str(exc))


memory_read_cache = MemoryReadCache()
