"""Redis-backed active agent run store."""

from __future__ import annotations

from datetime import UTC, datetime

import redis.asyncio as aioredis

from icore_agent.contexts.agent.application.runtime import (
    AgentRunRecord,
    QueuedAgentInput,
)

_KEY_PREFIX = "icore:agent:runtime"


class RedisAgentRunStore:
    """Store active run locks and control queues in Redis."""

    def __init__(
        self,
        *,
        redis_url: str,
        lock_ttl_seconds: int,
        state_ttl_seconds: int,
    ) -> None:
        """Create a Redis runtime store with explicit TTLs."""
        self._redis_url = redis_url
        self._lock_ttl_seconds = lock_ttl_seconds
        self._state_ttl_seconds = state_ttl_seconds
        self._redis: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        """Return the lazily-created Redis client."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        return self._redis

    async def try_acquire_run(self, record: AgentRunRecord) -> bool:
        """Acquire the per-session run lock when the session is idle."""
        redis = await self._get_client()
        acquired = await redis.set(
            f"{_KEY_PREFIX}:lock:{record.session_id}",
            record.run_id,
            nx=True,
            ex=self._lock_ttl_seconds,
        )
        if not acquired:
            return False
        await redis.set(
            f"{_KEY_PREFIX}:run:{record.session_id}",
            record.model_dump_json(),
            ex=self._state_ttl_seconds,
        )
        return True

    async def attach_turn_id(
        self,
        *,
        session_id: str,
        run_id: str,
        turn_id: str,
    ) -> None:
        """Attach the domain turn id to the active run metadata."""
        record = await self.get_active_run(session_id)
        if record is None or record.run_id != run_id:
            return
        updated = record.model_copy(update={"turn_id": turn_id})
        redis = await self._get_client()
        await redis.set(
            f"{_KEY_PREFIX}:run:{session_id}",
            updated.model_dump_json(),
            ex=self._state_ttl_seconds,
        )

    async def release_run(self, *, session_id: str, run_id: str) -> None:
        """Release the run lock if it still belongs to the same run."""
        redis = await self._get_client()
        current_run_id = await redis.get(f"{_KEY_PREFIX}:lock:{session_id}")
        if current_run_id != run_id:
            return
        await redis.delete(
            f"{_KEY_PREFIX}:lock:{session_id}",
            f"{_KEY_PREFIX}:run:{session_id}",
            f"{_KEY_PREFIX}:steer:{session_id}",
        )

    async def get_active_run(self, session_id: str) -> AgentRunRecord | None:
        """Return active run metadata when the Redis lock is still present."""
        redis = await self._get_client()
        lock_value = await redis.get(f"{_KEY_PREFIX}:lock:{session_id}")
        payload = await redis.get(f"{_KEY_PREFIX}:run:{session_id}")
        if not lock_value or not payload:
            if payload and not lock_value:
                await redis.delete(
                    f"{_KEY_PREFIX}:run:{session_id}",
                    f"{_KEY_PREFIX}:steer:{session_id}",
                )
            return None
        record = AgentRunRecord.model_validate_json(payload)
        if record.run_id != lock_value:
            return None
        return record

    async def request_abort(self, *, session_id: str, user_id: str) -> bool:
        """Mark the active run as abort requested."""
        record = await self.get_active_run(session_id)
        if record is None or record.user_id != user_id:
            return False
        updated = record.model_copy(update={"abort_requested": True})
        redis = await self._get_client()
        await redis.set(
            f"{_KEY_PREFIX}:run:{session_id}",
            updated.model_dump_json(),
            ex=self._state_ttl_seconds,
        )
        return True

    async def is_abort_requested(self, *, session_id: str, run_id: str) -> bool:
        """Return whether the active run has been asked to abort."""
        record = await self.get_active_run(session_id)
        return bool(
            record is not None
            and record.run_id == run_id
            and record.abort_requested
        )

    async def enqueue_steering(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> bool:
        """Queue current-turn steering input for an active run."""
        record = await self.get_active_run(session_id)
        if record is None or record.user_id != user_id:
            return False
        redis = await self._get_client()
        queued = QueuedAgentInput(
            message=message,
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        await redis.rpush(
            f"{_KEY_PREFIX}:steer:{session_id}",
            queued.model_dump_json(),
        )
        await redis.expire(
            f"{_KEY_PREFIX}:steer:{session_id}",
            self._state_ttl_seconds,
        )
        return True

    async def drain_steering(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> list[QueuedAgentInput]:
        """Return and clear queued current-turn steering inputs."""
        record = await self.get_active_run(session_id)
        if record is None or record.run_id != run_id:
            return []
        redis = await self._get_client()
        payloads = await redis.lrange(
            f"{_KEY_PREFIX}:steer:{session_id}",
            0,
            -1,
        )
        if not payloads:
            return []
        await redis.delete(f"{_KEY_PREFIX}:steer:{session_id}")
        return [
            QueuedAgentInput.model_validate_json(payload)
            for payload in payloads
        ]

    async def enqueue_follow_up(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> None:
        """Queue follow-up input for a later turn boundary."""
        redis = await self._get_client()
        queued = QueuedAgentInput(
            message=message,
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        await redis.rpush(
            f"{_KEY_PREFIX}:follow_up:{session_id}",
            queued.model_dump_json(),
        )
        await redis.expire(
            f"{_KEY_PREFIX}:follow_up:{session_id}",
            self._state_ttl_seconds,
        )

    async def aclose(self) -> None:
        """Close the underlying Redis connection when the process shuts down."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
