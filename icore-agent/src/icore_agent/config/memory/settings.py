from __future__ import annotations

from ..base import DomainSettings


class MemorySettings(DomainSettings):
    env_domains = ("memory",)

    redis_url: str = "redis://localhost:6379/0"
    memory_ttl_seconds: int = 86400
    memory_max_messages: int = 20
    memory_keep_recent: int = 8


memory_settings = MemorySettings()
