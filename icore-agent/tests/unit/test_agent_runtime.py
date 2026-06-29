"""Tests for the application AgentRuntime shell."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import pytest

from icore_agent.application.agent import AgentTurnCommand
from icore_agent.application.agent.runtime import (
    AgentRunConflict,
    AgentRunNotActive,
    AgentRunRecord,
    AgentRuntime,
    QueuedAgentInput,
)
from icore_agent.domain.agent.turn import TurnEvent
from icore_agent.domain.user import AuthenticatedUser


@pytest.mark.asyncio
async def test_agent_runtime_rejects_second_active_run_for_session() -> None:
    """Runtime should acquire a session run lock before turn preparation."""
    store = FakeRunStore()
    runtime = AgentRuntime(run_store=store)
    first_stream = await runtime.stream(_command(), _completed_events)

    with pytest.raises(AgentRunConflict):
        await runtime.stream(_command(), _completed_events)

    events = [event async for event in first_stream]

    assert [event.kind for event in events] == [
        "turn_started",
        "turn_completed",
    ]
    assert store.released_sessions == ["session-1"]


@pytest.mark.asyncio
async def test_agent_runtime_exposes_abort_to_running_event_source() -> None:
    """Abort requests should be durable and visible through the loop control."""
    runtime = AgentRuntime(run_store=FakeRunStore())
    stream = await runtime.stream(_command(), _abort_aware_events)

    task = _collect(stream)
    await runtime.abort(session_id="session-1", user_id="user-1")
    events = await task

    assert [event.kind for event in events] == [
        "turn_started",
        "turn_aborted",
    ]


@pytest.mark.asyncio
async def test_agent_runtime_queues_steering_and_follow_up_inputs() -> None:
    """Runtime control APIs should write steering and follow-up queues."""
    store = FakeRunStore()
    runtime = AgentRuntime(run_store=store)
    stream = await runtime.stream(_command(), _completed_events)

    steer_result = await runtime.steer(
        session_id="session-1",
        user_id="user-1",
        message="Change direction.",
    )
    follow_up_result = await runtime.follow_up(
        session_id="session-1",
        user_id="user-1",
        message="Next question.",
    )

    assert steer_result.accepted is True
    assert follow_up_result.accepted is True
    assert store.steering_messages == ["Change direction."]
    assert store.follow_up_messages == ["Next question."]
    _ = [event async for event in stream]


@pytest.mark.asyncio
async def test_agent_runtime_rejects_steer_without_active_run() -> None:
    """Steering is a current-turn input and requires an active run."""
    runtime = AgentRuntime(run_store=FakeRunStore())

    with pytest.raises(AgentRunNotActive):
        await runtime.steer(
            session_id="session-1",
            user_id="user-1",
            message="Too late.",
        )


async def _completed_events(
    control: Any,
) -> AsyncIterator[TurnEvent]:
    """Yield a deterministic successful runtime stream."""
    _ = control
    yield TurnEvent.turn_started(session_id="session-1", turn_id="turn-1")
    yield TurnEvent.turn_completed(
        session_id="session-1",
        turn_id="turn-1",
        reply="ok",
    )


async def _abort_aware_events(
    control: Any,
) -> AsyncIterator[TurnEvent]:
    """Yield an aborted stream after the runtime control observes abort."""
    yield TurnEvent.turn_started(session_id="session-1", turn_id="turn-1")
    while not await control.abort_requested():
        pass
    yield TurnEvent.turn_aborted(
        session_id="session-1",
        turn_id="turn-1",
        reply="",
    )


def _collect(events: AsyncIterator[TurnEvent]):
    """Collect an async stream in a task."""
    import asyncio

    async def _inner() -> list[TurnEvent]:
        return [event async for event in events]

    return asyncio.create_task(_inner())


def _command() -> AgentTurnCommand:
    """Build a deterministic runtime command."""
    return AgentTurnCommand(
        message="Hello",
        session_id="session-1",
        stream=True,
        tenant_code="",
        file_uuids=(),
        display_caption=None,
        agent_message=None,
        template_id=None,
        incognito=False,
        user=AuthenticatedUser(
            public_id="user-1",
            email="user@example.com",
            name="User One",
            roles=("owner",),
        ),
    )


class FakeRunStore:
    """In-memory AgentRunStore fake for runtime tests."""

    def __init__(self) -> None:
        """Create an empty fake runtime store."""
        self.active: AgentRunRecord | None = None
        self.abort_requested = False
        self.steering_messages: list[str] = []
        self.follow_up_messages: list[str] = []
        self.released_sessions: list[str] = []

    async def try_acquire_run(self, record: AgentRunRecord) -> bool:
        """Acquire the run when no active run exists."""
        if self.active is not None:
            return False
        self.active = record
        return True

    async def attach_turn_id(
        self,
        *,
        session_id: str,
        run_id: str,
        turn_id: str,
    ) -> None:
        """Record the turn id once the turn-start event is emitted."""
        assert self.active is not None
        assert self.active.session_id == session_id
        assert self.active.run_id == run_id
        self.active = self.active.model_copy(update={"turn_id": turn_id})

    async def release_run(self, *, session_id: str, run_id: str) -> None:
        """Release the active run lock."""
        assert self.active is not None
        assert self.active.session_id == session_id
        assert self.active.run_id == run_id
        self.released_sessions.append(session_id)
        self.active = None

    async def get_active_run(self, session_id: str) -> AgentRunRecord | None:
        """Return the active run for the session."""
        if self.active and self.active.session_id == session_id:
            return self.active
        return None

    async def request_abort(self, *, session_id: str, user_id: str) -> bool:
        """Mark the active run as aborted."""
        _ = user_id
        if self.active is None or self.active.session_id != session_id:
            return False
        self.abort_requested = True
        return True

    async def is_abort_requested(self, *, session_id: str, run_id: str) -> bool:
        """Return whether the active run has been asked to abort."""
        return (
            self.abort_requested
            and self.active is not None
            and self.active.session_id == session_id
            and self.active.run_id == run_id
        )

    async def enqueue_steering(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> bool:
        """Append one steering message when the session is active."""
        _ = user_id
        if self.active is None or self.active.session_id != session_id:
            return False
        self.steering_messages.append(message)
        return True

    async def drain_steering(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> list[QueuedAgentInput]:
        """Return and clear queued steering inputs."""
        if self.active is None or self.active.run_id != run_id:
            return []
        messages = list(self.steering_messages)
        self.steering_messages.clear()
        return [
            QueuedAgentInput(
                message=message,
                session_id=session_id,
                user_id="user-1",
                created_at=datetime.fromisoformat("2026-06-29T00:00:00+00:00"),
            )
            for message in messages
        ]

    async def enqueue_follow_up(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> None:
        """Append one follow-up message for later turn creation."""
        _ = (session_id, user_id)
        self.follow_up_messages.append(message)
