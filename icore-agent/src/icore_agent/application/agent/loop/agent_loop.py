"""Application-owned model/tool loop for one agent turn."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from icore_agent.domain.agent.session import (
    AgentMessageItem,
    SessionItemStatus,
    ToolCallItem,
    ToolCallStatus,
    ToolFunction,
)
from icore_agent.domain.agent.loop import (
    AgentLoopControl,
    ModelClient,
    ModelStreamWarning,
    ModelStepResult,
    ModelTextDelta,
    ModelToolCallCompleted,
    ModelToolCallDelta,
    ModelToolCallStarted,
    NoopAgentLoopControl,
    PromptContextManager,
    ToolRuntimePort,
)
from icore_agent.domain.agent.turn import Turn, TurnEvent
from icore_agent.shared.logging.app_logger import get_logger

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
    control: AgentLoopControl = field(default_factory=NoopAgentLoopControl)


class AgentLoopError(Exception):
    """Raised when the application agent loop cannot continue."""


class AgentLoopAborted(AgentLoopError):
    """Raised when the active run is cooperatively aborted."""


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
            await _raise_if_aborted(request)
            async for event in _drain_steering_events(request):
                yield event
            await _raise_if_aborted(request)
            envelope = request.context_manager.build_prompt(
                turn=request.turn,
                session_items=list(request.turn.items),
                tools=request.tool_runtime.visible_tools(),
            )
            try:
                stream = getattr(request.model_client, "stream", None)
                if callable(stream):
                    step = None
                    started_assistant = AgentMessageItem(
                        text="",
                        status=SessionItemStatus.IN_PROGRESS,
                    )
                    request.turn.upsert_item(started_assistant)
                    yield TurnEvent.item_started(
                        session_id=request.session_id,
                        turn_id=request.turn_id,
                        item=started_assistant,
                    )
                    streamed_text = ""
                    async for stream_event in stream(envelope):
                        if isinstance(stream_event, ModelTextDelta):
                            if not stream_event.text:
                                continue
                            streamed_text += stream_event.text
                            yield TurnEvent.item_delta(
                                session_id=request.session_id,
                                turn_id=request.turn_id,
                                item_id=started_assistant.id,
                                item_type="agent_message",
                                delta={"text_append": stream_event.text},
                            )
                            continue
                        if isinstance(stream_event, ModelToolCallStarted):
                            tool_call = _streaming_tool_call(stream_event)
                            request.turn.upsert_item(tool_call)
                            yield TurnEvent.item_started(
                                session_id=request.session_id,
                                turn_id=request.turn_id,
                                item=tool_call,
                            )
                            continue
                        if isinstance(stream_event, ModelToolCallDelta):
                            yield TurnEvent.item_delta(
                                session_id=request.session_id,
                                turn_id=request.turn_id,
                                item_id=stream_event.item_id,
                                item_type="tool_call",
                                delta={
                                    "arguments_append": stream_event.arguments_delta,
                                    "name": stream_event.name,
                                    "provider_tool_call_id": stream_event.provider_tool_call_id,
                                    "index": stream_event.index,
                                },
                            )
                            continue
                        if isinstance(stream_event, ModelToolCallCompleted):
                            request.turn.upsert_item(stream_event.tool_call)
                            yield TurnEvent.item_completed(
                                session_id=request.session_id,
                                turn_id=request.turn_id,
                                item=stream_event.tool_call,
                            )
                            continue
                        if isinstance(stream_event, ModelStreamWarning):
                            yield TurnEvent.stream_warning(
                                session_id=request.session_id,
                                turn_id=request.turn_id,
                                code=stream_event.code,
                                message=stream_event.message,
                                retryable=stream_event.retryable,
                            )
                            continue
                        step = stream_event
                    if step is None:
                        step = ModelStepResult(
                            assistant_item=AgentMessageItem(
                                text=streamed_text,
                            ),
                        )
                    assistant_item = _completed_assistant_item(
                        step.assistant_item.model_copy(update={
                            "id": started_assistant.id,
                            "text": step.assistant_item.text
                            or streamed_text,
                        }),
                    )
                    step = ModelStepResult(
                        assistant_item=assistant_item,
                        tool_calls=step.tool_calls,
                        deltas=[],
                        usage=step.usage,
                        model=step.model,
                        provider=step.provider,
                        stop_reason=step.stop_reason,
                        raw_response_id=step.raw_response_id,
                        raw_payload=step.raw_payload,
                    )
                    request.turn.upsert_item(assistant_item)
                    yield TurnEvent.item_completed(
                        session_id=request.session_id,
                        turn_id=request.turn_id,
                        item=assistant_item,
                    )
                else:
                    step = await request.model_client.sample(envelope)
            except Exception as exc:
                log.error("agent_model_step_failed", error=str(exc))
                raise AgentLoopError(str(exc)) from exc

            if not callable(stream):
                started_assistant = _started_assistant_item(
                    step.assistant_item)
                assistant_item = _completed_assistant_item(
                    step.assistant_item)
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
                        item_type="agent_message",
                        delta={"text_append": delta},
                    )
                yield TurnEvent.item_completed(
                    session_id=request.session_id,
                    turn_id=request.turn_id,
                    item=assistant_item,
                )

            if step.stop_reason in {"error", "aborted"}:
                if step.stop_reason == "aborted":
                    raise AgentLoopAborted("agent run aborted")
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


async def _raise_if_aborted(request: AgentLoopRequest) -> None:
    """Raise AgentLoopAborted when runtime control requests abort."""
    if await request.control.abort_requested():
        raise AgentLoopAborted("agent run aborted")


async def _drain_steering_events(
    request: AgentLoopRequest,
) -> AsyncIterator[TurnEvent]:
    """Persist runtime steering input as current-turn user item events."""
    for item in await request.control.drain_steering():
        request.turn.upsert_item(item)
        yield TurnEvent.item_completed(
            session_id=request.session_id,
            turn_id=request.turn_id,
            item=item,
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
        "status": ToolCallStatus.RUNNING,
        "created_at": item.created_at,
        "started_at": item.started_at or datetime.now(UTC),
        "completed_at": None,
    })


def _streaming_tool_call(event: ModelToolCallStarted) -> ToolCallItem:
    """Build a timeline item for a provider-streaming tool call."""
    return ToolCallItem(
        id=event.item_id,
        status=ToolCallStatus.STREAMING,
        provider_tool_call_id=event.provider_tool_call_id,
        index=event.index,
        function=ToolFunction(
            name=event.name,
            arguments_text="",
        ),
        started_at=datetime.now(UTC),
    )
