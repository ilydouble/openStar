"""Tests for the Redis AgentRunStore adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from icore_agent.application.agent.runtime import AgentRunRecord
from icore_agent.infrastructure.agent.runtime import RedisAgentRunStore


@pytest.mark.asyncio
async def test_redis_agent_run_store_coordinates_active_run(monkeypatch) -> None:
    """Redis store should lock, control, drain, and release active runs."""
    redis = FakeAsyncRedis()

    async def fake_from_url(*_: Any, **__: Any) -> FakeAsyncRedis:
        """Return the fake Redis client."""
        return redis

    monkeypatch.setattr(
        "icore_agent.infrastructure.agent.runtime.redis_store.aioredis.from_url",
        fake_from_url,
    )
    store = RedisAgentRunStore(
        redis_url="redis://localhost:6379/0",
        lock_ttl_seconds=1200,
        state_ttl_seconds=3600,
    )
    record = AgentRunRecord(
        run_id="run-1",
        session_id="session-1",
        user_id="user-1",
        started_at=datetime.fromisoformat("2026-06-29T00:00:00+00:00"),
    )

    assert await store.try_acquire_run(record) is True
    assert await store.try_acquire_run(record.model_copy(update={"run_id": "run-2"})) is False
    await store.attach_turn_id(
        session_id="session-1",
        run_id="run-1",
        turn_id="turn-1",
    )
    active = await store.get_active_run("session-1")
    assert active is not None
    assert active.turn_id == "turn-1"

    assert await store.enqueue_steering(
        session_id="session-1",
        user_id="user-1",
        message="Change direction.",
    ) is True
    queued = await store.drain_steering(session_id="session-1", run_id="run-1")
    assert [item.message for item in queued] == ["Change direction."]
    assert await store.drain_steering(session_id="session-1", run_id="run-1") == []

    assert await store.request_abort(session_id="session-1", user_id="user-1") is True
    assert await store.is_abort_requested(session_id="session-1", run_id="run-1") is True

    await store.release_run(session_id="session-1", run_id="run-1")
    assert await store.get_active_run("session-1") is None


class FakeAsyncRedis:
    """Small async Redis fake for runtime store tests."""

    def __init__(self) -> None:
        """Create empty string and list stores."""
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool:
        """Set one string value with optional NX semantics."""
        _ = ex
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        """Return a stored string value."""
        return self.values.get(key)

    async def delete(self, *keys: str) -> int:
        """Delete string and list keys."""
        removed = 0
        for key in keys:
            if key in self.values:
                removed += 1
                self.values.pop(key, None)
            if key in self.lists:
                removed += 1
                self.lists.pop(key, None)
        return removed

    async def rpush(self, key: str, value: str) -> int:
        """Append one list value."""
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        """Return list values for the requested range."""
        values = self.lists.get(key, [])
        if start == 0 and stop == -1:
            return list(values)
        return values[start:stop + 1]

    async def expire(self, key: str, seconds: int) -> bool:
        """Accept key expiration requests."""
        _ = (key, seconds)
        return True
