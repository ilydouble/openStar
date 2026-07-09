"""Application ports for active agent run state."""

from __future__ import annotations

from typing import Protocol

from .models import AgentRunRecord, QueuedAgentInput


class AgentRunStore(Protocol):
    """Store active run state and runtime control queues."""

    async def try_acquire_run(self, record: AgentRunRecord) -> bool:
        """Create an active run lock when the session is idle."""
        ...

    async def attach_turn_id(
        self,
        *,
        session_id: str,
        run_id: str,
        turn_id: str,
    ) -> None:
        """Attach the persisted turn id to an active run."""
        ...

    async def release_run(self, *, session_id: str, run_id: str) -> None:
        """Release the active run lock for a finished run."""
        ...

    async def get_active_run(self, session_id: str) -> AgentRunRecord | None:
        """Return the active run for a session, if one exists."""
        ...

    async def request_abort(self, *, session_id: str, user_id: str) -> bool:
        """Mark the active run as abort requested."""
        ...

    async def is_abort_requested(self, *, session_id: str, run_id: str) -> bool:
        """Return whether the active run has been asked to abort."""
        ...

    async def enqueue_steering(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> bool:
        """Queue current-turn steering input for an active run."""
        ...

    async def drain_steering(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> list[QueuedAgentInput]:
        """Return and clear queued current-turn steering inputs."""
        ...

    async def enqueue_follow_up(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> None:
        """Queue follow-up input for later turn creation."""
        ...
