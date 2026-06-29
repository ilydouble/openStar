"""Stateful application shell above the thin AgentLoop."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from icore_agent.domain.agent.turn import AgentTurnCommand
from icore_agent.domain.agent.session import (
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.turn import TurnEvent, TurnEventKind
from icore_agent.domain.identifiers import uuid7

from .exceptions import AgentRunConflict, AgentRunNotActive
from .models import AgentRunControlResult, AgentRunRecord, QueuedAgentInput
from .ports import AgentRunStore

AgentRuntimeEventSource = Callable[[
    "AgentRunControl"], AsyncIterator[TurnEvent]]


@dataclass(slots=True)
class _LocalActiveRun:
    """Process-local handles for a run that may be controlled in-process."""

    record: AgentRunRecord
    abort_event: asyncio.Event = field(default_factory=asyncio.Event)
    idle_event: asyncio.Event = field(default_factory=asyncio.Event)


class AgentRunControl:
    """Loop-facing control view for one active agent run."""

    def __init__(
        self,
        *,
        store: AgentRunStore,
        local_run: _LocalActiveRun,
    ) -> None:
        """Create a control object bound to one active run."""
        self._store = store
        self._local_run = local_run

    async def abort_requested(self) -> bool:
        """Return whether the current run should abort cooperatively."""
        record = self._local_run.record
        if self._local_run.abort_event.is_set():
            return True
        return await self._store.is_abort_requested(
            session_id=record.session_id,
            run_id=record.run_id,
        )

    async def drain_steering(self) -> list[UserMessageItem]:
        """Drain queued steering input as current-turn user message items."""
        record = self._local_run.record
        queued = await self._store.drain_steering(
            session_id=record.session_id,
            run_id=record.run_id,
        )
        return [_steering_item(item) for item in queued]


class AgentRuntime:
    """Own active run state, cancellation, steering, and idle coordination."""

    def __init__(self, *, run_store: AgentRunStore) -> None:
        """Create a runtime shell backed by an AgentRunStore."""
        self._run_store = run_store
        self._local_runs: dict[str, _LocalActiveRun] = {}
        self._local_lock = asyncio.Lock()

    async def stream(
        self,
        command: AgentTurnCommand,
        event_source: AgentRuntimeEventSource,
    ) -> AsyncIterator[TurnEvent]:
        """Acquire a session run and return a wrapped turn event stream."""
        run = await self._begin_run(command)
        control = AgentRunControl(store=self._run_store, local_run=run)

        async def _wrapped() -> AsyncIterator[TurnEvent]:
            attached_turn = False
            try:
                async for event in event_source(control):
                    if (
                        not attached_turn
                        and event.kind is TurnEventKind.TURN_STARTED
                    ):
                        attached_turn = True
                        await self._attach_turn(run, event.turn_id)
                    yield event
            finally:
                await self._finish_run(run)

        return _wrapped()

    async def abort(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> AgentRunControlResult:
        """Request cooperative abort for an active session run."""
        accepted = await self._run_store.request_abort(
            session_id=session_id,
            user_id=user_id,
        )
        if not accepted:
            raise AgentRunNotActive("no active agent run")
        local_run = await self._local_run(session_id)
        if local_run is not None:
            local_run.abort_event.set()
        record = await self._run_store.get_active_run(session_id)
        return AgentRunControlResult(
            accepted=True,
            session_id=session_id,
            run_id=record.run_id if record else None,
        )

    async def steer(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> AgentRunControlResult:
        """Queue a current-turn steering message for an active run."""
        accepted = await self._run_store.enqueue_steering(
            session_id=session_id,
            user_id=user_id,
            message=message,
        )
        if not accepted:
            raise AgentRunNotActive("no active agent run")
        record = await self._run_store.get_active_run(session_id)
        return AgentRunControlResult(
            accepted=True,
            session_id=session_id,
            run_id=record.run_id if record else None,
        )

    async def follow_up(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> AgentRunControlResult:
        """Queue follow-up input for a later turn boundary."""
        await self._run_store.enqueue_follow_up(
            session_id=session_id,
            user_id=user_id,
            message=message,
        )
        record = await self._run_store.get_active_run(session_id)
        return AgentRunControlResult(
            accepted=True,
            session_id=session_id,
            run_id=record.run_id if record else None,
        )

    async def wait_for_idle(
        self,
        session_id: str,
        *,
        timeout: float | None = None,
    ) -> bool:
        """Wait until the session has no active runtime run."""
        local_run = await self._local_run(session_id)
        if local_run is not None:
            await asyncio.wait_for(local_run.idle_event.wait(), timeout)
            return True

        async def _poll_store() -> None:
            while await self._run_store.get_active_run(session_id) is not None:
                await asyncio.sleep(0.1)

        await asyncio.wait_for(_poll_store(), timeout)
        return True

    async def _begin_run(self, command: AgentTurnCommand) -> _LocalActiveRun:
        """Create a durable active run record before turn preparation."""
        record = AgentRunRecord(
            run_id=str(uuid7()),
            session_id=command.session_id,
            user_id=command.user_id,
            started_at=datetime.now(UTC),
        )
        acquired = await self._run_store.try_acquire_run(record)
        if not acquired:
            raise AgentRunConflict(
                f"session {command.session_id} already has an active agent run",
            )
        local_run = _LocalActiveRun(record=record)
        async with self._local_lock:
            self._local_runs[command.session_id] = local_run
        return local_run

    async def _attach_turn(
        self,
        local_run: _LocalActiveRun,
        turn_id: str,
    ) -> None:
        """Attach a turn id to the active run after turn start."""
        record = local_run.record
        await self._run_store.attach_turn_id(
            session_id=record.session_id,
            run_id=record.run_id,
            turn_id=turn_id,
        )
        local_run.record = record.model_copy(update={"turn_id": turn_id})

    async def _finish_run(self, local_run: _LocalActiveRun) -> None:
        """Release durable and local active-run state."""
        record = local_run.record
        try:
            await self._run_store.release_run(
                session_id=record.session_id,
                run_id=record.run_id,
            )
        finally:
            async with self._local_lock:
                existing = self._local_runs.get(record.session_id)
                if existing is local_run:
                    self._local_runs.pop(record.session_id, None)
            local_run.idle_event.set()

    async def _local_run(self, session_id: str) -> _LocalActiveRun | None:
        """Return the local active run for a session, if this process owns it."""
        async with self._local_lock:
            return self._local_runs.get(session_id)


def _steering_item(queued: QueuedAgentInput) -> UserMessageItem:
    """Convert queued steering input to a model-visible session item."""
    return UserMessageItem(
        content=[
            UserInput(
                type=UserInputType.TEXT,
                text=queued.message,
            )
        ],
        metadata={
            "runtime_input": "steering",
            "queued_user_id": queued.user_id,
        },
        created_at=queued.created_at,
        completed_at=queued.created_at,
    )
