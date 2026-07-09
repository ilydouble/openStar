"""Tests for workspace Redis cache degradation."""

from __future__ import annotations

from typing import Any

import redis

from icore_agent.contexts.account.infrastructure.cache import workspace_cache as workspace_cache_module


class BrokenRedis:
    """Redis fake that fails every operation."""

    def get(self, *args: Any, **kwargs: Any) -> None:
        """Raise the same error shape as redis-py operations."""
        raise redis.ConnectionError("redis unavailable")

    def set(self, *args: Any, **kwargs: Any) -> None:
        """Raise the same error shape as redis-py operations."""
        raise redis.ConnectionError("redis unavailable")

    def delete(self, *args: Any, **kwargs: Any) -> None:
        """Raise the same error shape as redis-py operations."""
        raise redis.ConnectionError("redis unavailable")


class FakeLogger:
    """Logger fake that records warning calls without external I/O."""

    def __init__(self) -> None:
        """Create an empty warning recorder."""
        self.warnings: list[tuple[str, dict[str, Any]]] = []

    def warning(self, event: str, **kwargs: Any) -> None:
        """Record one warning event."""
        self.warnings.append((event, kwargs))


def test_workspace_cache_degrades_when_redis_is_unavailable(monkeypatch) -> None:
    """Redis cache failures should not break workspace account flows."""
    logger = FakeLogger()
    monkeypatch.setattr(workspace_cache_module, "log", logger)
    cache = workspace_cache_module.WorkspaceCache()
    cache._client = BrokenRedis()

    assert cache.get_team_profile("user-1") is None
    assert cache.get_project_list("user-1") is None
    cache.set_team_profile("user-1", {"team": "demo"})
    cache.set_project_list("user-1", {"projects": []})
    cache.invalidate_user("user-1")

    assert [event for event, _kwargs in logger.warnings] == [
        "workspace_cache_unavailable",
        "workspace_cache_unavailable",
        "workspace_cache_unavailable",
        "workspace_cache_unavailable",
        "workspace_cache_unavailable",
    ]
