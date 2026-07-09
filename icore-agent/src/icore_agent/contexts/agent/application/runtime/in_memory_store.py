"""In-memory AgentRunStore used by unit tests and local fallback wiring."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from .models import AgentRunRecord, QueuedAgentInput


class InMemoryAgentRunStore:
    """Process-local active run store with the AgentRunStore interface."""

    def __init__(self) -> None:
        """Create an empty process-local runtime store."""
        self._lock = asyncio.Lock()
        self._active: dict[str, AgentRunRecord] = {}
        self._steering: dict[str, list[QueuedAgentInput]] = {}
        self._follow_up: dict[str, list[QueuedAgentInput]] = {}

    async def try_acquire_run(self, record: AgentRunRecord) -> bool:
        """Acquire a session run lock when no active run exists."""
        async with self._lock:
            if record.session_id in self._active:
                return False
            self._active[record.session_id] = record
            return True

    async def attach_turn_id(
        self,
        *,
        session_id: str,
        run_id: str,
        turn_id: str,
    ) -> None:
        """Attach the domain turn id to an active run."""
        async with self._lock:
            record = self._active.get(session_id)
            if record is None or record.run_id != run_id:
                return
            self._active[session_id] = record.model_copy(
                update={"turn_id": turn_id},
            )

    async def release_run(self, *, session_id: str, run_id: str) -> None:
        """Release an active run lock and clear stale steering input."""
        async with self._lock:
            record = self._active.get(session_id)
            if record is None or record.run_id != run_id:
                return
            self._active.pop(session_id, None)
            self._steering.pop(session_id, None)

    async def get_active_run(self, session_id: str) -> AgentRunRecord | None:
        """Return the active run for a session."""
        async with self._lock:
            return self._active.get(session_id)

    async def request_abort(self, *, session_id: str, user_id: str) -> bool:
        """Mark the active run as abort requested."""
        async with self._lock:
            record = self._active.get(session_id)
            if record is None or record.user_id != user_id:
                return False
            self._active[session_id] = record.model_copy(
                update={"abort_requested": True},
            )
            return True

    async def is_abort_requested(self, *, session_id: str, run_id: str) -> bool:
        """Return whether the active run has been asked to abort."""
        async with self._lock:
            record = self._active.get(session_id)
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
        """Queue steering input only when the session has an active run."""
        async with self._lock:
            record = self._active.get(session_id)
            if record is None or record.user_id != user_id:
                return False
            self._steering.setdefault(session_id, []).append(
                QueuedAgentInput(
                    message=message,
                    session_id=session_id,
                    user_id=user_id,
                    created_at=datetime.now(UTC),
                )
            )
            return True

    async def drain_steering(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> list[QueuedAgentInput]:
        """Return and clear all queued steering input for one active run."""
        async with self._lock:
            record = self._active.get(session_id)
            if record is None or record.run_id != run_id:
                return []
            items = list(self._steering.get(session_id, []))
            self._steering[session_id] = []
            return items

    async def enqueue_follow_up(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> None:
        """Queue follow-up input for later turn creation."""
        async with self._lock:
            self._follow_up.setdefault(session_id, []).append(
                QueuedAgentInput(
                    message=message,
                    session_id=session_id,
                    user_id=user_id,
                    created_at=datetime.now(UTC),
                )
            )
