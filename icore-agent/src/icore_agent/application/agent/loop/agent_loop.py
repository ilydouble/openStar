"""Application-owned model/tool loop for one agent turn."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from icore_agent.domain.agent.session import (
    AgentMessageItem,
    SessionItemStatus,
    ToolCallItem,
)
from icore_agent.domain.agent.turn import Turn, TurnEvent
from icore_agent.shared.logging.app_logger import get_logger

from .types import ModelClient, PromptContextManager, ToolRuntimePort

log = get_logger(__name__)

_DEFAULT_MAX_TOOL_ROUNDS = 8


@dataclass(slots=True)
class AgentLoopRequest:
    """Inputs needed to run one application-level agent loop."""

    session_id: str
    turn_id: str
    turn: Turn
    context_manager: PromptContextManager
    model_client: ModelClient
    tool_runtime: ToolRuntimePort
    max_tool_rounds: int = _DEFAULT_MAX_TOOL_ROUNDS


class AgentLoopError(Exception):
    """Raised when the application agent loop cannot continue."""


class AgentLoop:
    """Run the model-tool loop and emit item-level turn events."""

    def __init__(self, *, wall_budget_sec: int) -> None:
        """Create a loop with a hard wall-clock budget."""
        self._wall_budget_sec = wall_budget_sec

    async def run(self, request: AgentLoopRequest) -> AsyncIterator[TurnEvent]:
        """Run model sampling and tool execution until the assistant stops."""
        start = asyncio.get_running_loop().time()
        tool_rounds = 0
        while True:
            self._raise_if_over_budget(start)
            envelope = request.context_manager.build_prompt(
                turn=request.turn,
                session_items=list(request.turn.items),
                tools=request.tool_runtime.visible_tools(),
            )
            try:
                step = await request.model_client.sample(envelope)
            except Exception as exc:
                log.error("agent_model_step_failed", error=str(exc))
                raise AgentLoopError(str(exc)) from exc

            started_assistant = _started_assistant_item(step.assistant_item)
            assistant_item = _completed_assistant_item(step.assistant_item)
            request.turn.upsert_item(started_assistant)
            yield TurnEvent.item_started(
                session_id=request.session_id,
                turn_id=request.turn_id,
                item=started_assistant,
            )
            request.turn.upsert_item(assistant_item)
            for delta in step.deltas:
                yield TurnEvent.item_delta(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    item_id=assistant_item.id,
                    delta={"text": delta},
                )
            yield TurnEvent.item_completed(
                session_id=request.session_id,
                turn_id=request.turn_id,
                item=assistant_item,
            )

            if step.stop_reason in {"error", "aborted"}:
                raise AgentLoopError(
                    f"model step stopped with {step.stop_reason}",
                )
            if not step.tool_calls:
                return
            if tool_rounds >= request.max_tool_rounds:
                raise AgentLoopError(
                    "Chat Completions tool loop exceeded limit")
            tool_rounds += 1

            requested_calls = [
                _running_tool_call(tool_call)
                for tool_call in step.tool_calls
            ]
            for tool_call in requested_calls:
                request.turn.upsert_item(tool_call)
                yield TurnEvent.item_started(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    item=tool_call,
                )

            try:
                completed_calls = await request.tool_runtime.execute(
                    requested_calls,
                )
            except Exception as exc:
                log.error("agent_tool_runtime_failed", error=str(exc))
                raise AgentLoopError(str(exc)) from exc
            for tool_call in completed_calls:
                request.turn.upsert_item(tool_call)
                yield TurnEvent.item_completed(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    item=tool_call,
                )

    def _raise_if_over_budget(self, start: float) -> None:
        """Raise when the loop exceeds its wall-clock budget."""
        loop = asyncio.get_running_loop()
        if loop.time() - start <= self._wall_budget_sec:
            return
        raise AgentLoopError(
            f"Agent run exceeded {self._wall_budget_sec}s budget",
        )


def _started_assistant_item(item: AgentMessageItem) -> AgentMessageItem:
    """Return an assistant item marked as in progress."""
    return item.model_copy(update={
        "status": SessionItemStatus.IN_PROGRESS,
        "completed_at": None,
    })


def _completed_assistant_item(item: AgentMessageItem) -> AgentMessageItem:
    """Return an assistant item marked as completed."""
    return item.model_copy(update={
        "status": SessionItemStatus.COMPLETED,
        "completed_at": item.completed_at or datetime.now(UTC),
    })


def _running_tool_call(item: ToolCallItem) -> ToolCallItem:
    """Return a tool-call item ready to execute in the current turn."""
    return item.model_copy(update={
        "status": item.status,
        "created_at": item.created_at,
        "started_at": item.started_at or datetime.now(UTC),
        "completed_at": None,
    })
