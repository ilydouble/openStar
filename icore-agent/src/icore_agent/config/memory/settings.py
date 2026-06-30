from __future__ import annotations

from ..base import DomainSettings


class MemorySettings(DomainSettings):
    env_domains = ("memory",)

    redis_url: str = "redis://localhost:6379/0"
    memory_ttl_seconds: int = 86400
    memory_max_messages: int = 20
    memory_keep_recent: int = 8
    # Short read-through cache for build_memory_prompt()'s Postgres lookups
    # (profile + active facts). These rows only change on session-end
    # extraction or explicit account-memory edits, so a short TTL plus
    # explicit invalidation on every write keeps staleness bounded while
    # removing the DB round-trip from the per-turn hot path.
    memory_read_cache_ttl_seconds: int = 120


memory_settings = MemorySettings()
