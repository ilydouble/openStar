"""Agent runtime settings."""

from __future__ import annotations

from ..base import DomainSettings


class AgentSettings(DomainSettings):
    """Settings for agent runtime coordination."""

    env_domains = ("agent",)

    agent_runtime_lock_ttl_seconds: int = 1200
    agent_runtime_state_ttl_seconds: int = 3600


agent_settings = AgentSettings()
