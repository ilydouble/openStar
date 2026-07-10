"""Tests for the application-owned agent model/tool loop."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from icore_agent.contexts.agent.application.loop import (
    AgentLoop,
    AgentLoopAborted,
    AgentLoopError,
    AgentLoopRequest,
)
from icore_agent.contexts.agent.domain.loop import (
    ModelReasoningDelta,
    ModelStepResult,
    ModelTextDelta,
    ModelToolCallCompleted,
    ModelToolCallDelta,
    ModelToolCallStarted,
)
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ReasoningItem,
    SessionItem,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.tool import ToolChoice, ToolDefinition
from icore_agent.contexts.agent.domain.turn import Turn, TurnEventKind


@pytest.mark.asyncio
async def test_agent_loop_owns_tool_cycle_between_model_samples() -> None:
    """AgentLoop should sample, execute tool calls, then sample again."""
    turn = Turn(session_id="session-1")
    user_item = UserMessageItem(content=[
        UserInput(type=UserInputType.TEXT, text="Which number is bigger?"),
    ])
    turn.upsert_item(user_item)
    model_client = ScriptedModelClient([
        ModelStepResult(
            assistant_item=AgentMessageItem(text=""),
            reasoning_item=ReasoningItem(
                text="The comparator is appropriate."),
            tool_calls=[_tool_call()],
        ),
        ModelStepResult(
            assistant_item=AgentMessageItem(text="2 is greater than 1."),
        ),
    ])
    request = AgentLoopRequest(
        session_id="session-1",
        turn_id=turn.id,
        turn=turn,
        context_manager=RecordingContextManager(),
        model_client=model_client,
        tool_runtime=CompletingToolRuntime(),
    )

    events = [event async for event in AgentLoop(wall_budget_sec=60).run(request)]

    assert [event.kind for event in events] == [
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_COMPLETED,
    ]
    assert model_client.prompt_turn_item_types == [
        [],
        ["agent_message", "reasoning", "tool_call"],
    ]
    assert turn.reply_text() == "2 is greater than 1."


@pytest.mark.asyncio
async def test_agent_loop_drains_steering_before_next_model_sample() -> None:
    """Runtime steering should become a current-turn user item before resampling."""
    turn = Turn(session_id="session-1")
    turn.upsert_item(UserMessageItem(content=[
        UserInput(type=UserInputType.TEXT, text="Initial request"),
    ]))
    model_client = ScriptedModelClient([
        ModelStepResult(
            assistant_item=AgentMessageItem(text=""),
            tool_calls=[_tool_call()],
        ),
        ModelStepResult(
            assistant_item=AgentMessageItem(text="steered reply"),
        ),
    ])
    request = AgentLoopRequest(
        session_id="session-1",
        turn_id=turn.id,
        turn=turn,
        context_manager=RecordingContextManager(),
        model_client=model_client,
        tool_runtime=CompletingToolRuntime(),
        control=SteeringControl("Please revise the approach."),
    )

    events = [event async for event in AgentLoop(wall_budget_sec=60).run(request)]

    assert events[-1].item.text == "steered reply"
    assert model_client.prompt_turn_item_types == [
        [],
        ["agent_message", "tool_call", "user_message"],
    ]
    assert any(
        isinstance(item, UserMessageItem)
        and item.to_text() == "Please revise the approach."
        for item in turn.items
    )


@pytest.mark.asyncio
async def test_agent_loop_emits_model_streaming_deltas_before_completion() -> None:
    """AgentLoop should expose streaming model text as item_delta events."""
    turn = Turn(session_id="session-1")
    request = AgentLoopRequest(
        session_id="session-1",
        turn_id=turn.id,
        turn=turn,
        context_manager=RecordingContextManager(),
        model_client=StreamingModelClient(),
        tool_runtime=CompletingToolRuntime(),
    )

    events = [event async for event in AgentLoop(wall_budget_sec=60).run(request)]

    assert [event.kind for event in events] == [
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_COMPLETED,
    ]
    assert [event.delta for event in events if event.delta] == [
        {"text_append": "Hel"},
        {"text_append": "lo"},
    ]
    assert events[-1].item.text == "Hello"
    assert events[1].item_id == events[0].item.id


@pytest.mark.asyncio
async def test_agent_loop_emits_and_persists_streaming_reasoning_item() -> None:
    """AgentLoop should expose reasoning without adding it to final reply text."""
    turn = Turn(session_id="session-1")
    request = AgentLoopRequest(
        session_id="session-1",
        turn_id=turn.id,
        turn=turn,
        context_manager=RecordingContextManager(),
        model_client=StreamingReasoningModelClient(),
        tool_runtime=CompletingToolRuntime(),
    )

    events = [event async for event in AgentLoop(wall_budget_sec=60).run(request)]
    reasoning_events = [
        event
        for event in events
        if event.item_type == "reasoning"
        or isinstance(event.item, ReasoningItem)
    ]

    assert [event.kind for event in reasoning_events] == [
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_COMPLETED,
    ]
    assert [event.delta for event in reasoning_events if event.delta] == [
        {"text_append": "Inspect "},
        {"text_append": "the evidence."},
    ]
    assert reasoning_events[-1].item.text == "Inspect the evidence."
    assert any(
        isinstance(item, ReasoningItem)
        and item.text == "Inspect the evidence."
        for item in turn.items
    )
    assert turn.reply_text() == "Final answer"


@pytest.mark.asyncio
async def test_agent_loop_exposes_streaming_tool_call_deltas() -> None:
    """AgentLoop should project provider tool-call chunks into item deltas."""
    turn = Turn(session_id="session-1")
    request = AgentLoopRequest(
        session_id="session-1",
        turn_id=turn.id,
        turn=turn,
        context_manager=RecordingContextManager(),
        model_client=StreamingToolCallModelClient(),
        tool_runtime=CompletingToolRuntime(),
    )

    events = [event async for event in AgentLoop(wall_budget_sec=60).run(request)]
    tool_events = [
        event
        for event in events
        if event.item_id == "tool-item-1"
        or (event.item is not None and event.item.id == "tool-item-1")
    ]

    assert [event.kind for event in tool_events] == [
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_DELTA,
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_COMPLETED,
    ]
    assert tool_events[0].item.status == ToolCallStatus.STREAMING
    assert tool_events[1].delta == {
        "arguments_append": '{"left":',
        "name": "number_comparator",
        "provider_tool_call_id": "provider-tool-1",
        "index": 0,
    }
    assert tool_events[2].delta == {
        "arguments_append": '2,"right":1}',
        "name": "number_comparator",
        "provider_tool_call_id": "provider-tool-1",
        "index": 0,
    }
    assert tool_events[3].item.status == ToolCallStatus.READY
    assert tool_events[4].item.status == ToolCallStatus.RUNNING
    assert tool_events[-1].item.status == ToolCallStatus.COMPLETED


@pytest.mark.asyncio
async def test_agent_loop_fails_when_tool_round_limit_is_exceeded() -> None:
    """AgentLoop should fail fast when the model keeps requesting tools."""
    turn = Turn(session_id="session-1")
    model_client = ScriptedModelClient([
        ModelStepResult(
            assistant_item=AgentMessageItem(text=""),
            tool_calls=[_tool_call()],
        ),
    ])
    request = AgentLoopRequest(
        session_id="session-1",
        turn_id=turn.id,
        turn=turn,
        context_manager=RecordingContextManager(),
        model_client=model_client,
        tool_runtime=CompletingToolRuntime(),
        max_tool_rounds=0,
    )

    with pytest.raises(AgentLoopError, match="tool loop exceeded"):
        _ = [event async for event in AgentLoop(wall_budget_sec=60).run(request)]


@pytest.mark.asyncio
async def test_agent_loop_aborts_before_model_sampling_when_requested() -> None:
    """AgentLoop should stop cooperatively before calling the model client."""
    turn = Turn(session_id="session-1")
    request = AgentLoopRequest(
        session_id="session-1",
        turn_id=turn.id,
        turn=turn,
        context_manager=RecordingContextManager(),
        model_client=FailingModelClient(),
        tool_runtime=CompletingToolRuntime(),
        control=AbortControl(),
    )

    with pytest.raises(AgentLoopAborted):
        _ = [event async for event in AgentLoop(wall_budget_sec=60).run(request)]


class ScriptedModelClient:
    """Model client fake that returns preconfigured step results."""

    def __init__(self, steps: list[ModelStepResult]) -> None:
        """Create the fake model client with ordered responses."""
        self._steps = list(steps)
        self.prompt_turn_item_types: list[list[str]] = []

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Return the next scripted model result."""
        self.prompt_turn_item_types.append(
            [
                str(item.type)
                for item in envelope.turn_items
            ],
        )
        return self._steps.pop(0)


class StreamingModelClient:
    """Model client fake that streams text before returning the final step."""

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Fail if AgentLoop falls back to non-streaming sampling."""
        _ = envelope
        raise AssertionError("AgentLoop should use stream() when available")

    async def stream(self, envelope: PromptEnvelope):
        """Yield text deltas followed by the final model step."""
        _ = envelope
        yield ModelTextDelta(text="Hel")
        yield ModelTextDelta(text="lo")
        yield ModelStepResult(
            assistant_item=AgentMessageItem(text="Hello"),
        )


class StreamingReasoningModelClient:
    """Model client fake that streams reasoning separately from answer text."""

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Fail if AgentLoop falls back to non-streaming sampling."""
        _ = envelope
        raise AssertionError("AgentLoop should use stream() when available")

    async def stream(self, envelope: PromptEnvelope):
        """Yield reasoning, final text, and a completed model result."""
        _ = envelope
        yield ModelReasoningDelta(text="Inspect ")
        yield ModelReasoningDelta(text="the evidence.")
        yield ModelTextDelta(text="Final answer")
        yield ModelStepResult(
            assistant_item=AgentMessageItem(text="Final answer"),
            reasoning_item=ReasoningItem(text="Inspect the evidence."),
        )


class StreamingToolCallModelClient:
    """Model client fake that streams a tool call before returning a step."""

    def __init__(self) -> None:
        """Create the fake with one tool-call round."""
        self._calls = 0

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Fail if AgentLoop falls back to non-streaming sampling."""
        _ = envelope
        raise AssertionError("AgentLoop should use stream() when available")

    async def stream(self, envelope: PromptEnvelope):
        """Yield tool-call stream events followed by a final model step."""
        _ = envelope
        self._calls += 1
        if self._calls > 1:
            yield ModelTextDelta(text="Done")
            yield ModelStepResult(
                assistant_item=AgentMessageItem(text="Done"),
                stop_reason="stop",
            )
            return
        yield ModelToolCallStarted(
            item_id="tool-item-1",
            provider_tool_call_id="provider-tool-1",
            index=0,
            name="number_comparator",
        )
        yield ModelToolCallDelta(
            item_id="tool-item-1",
            provider_tool_call_id="provider-tool-1",
            index=0,
            name="number_comparator",
            arguments_delta='{"left":',
        )
        yield ModelToolCallDelta(
            item_id="tool-item-1",
            provider_tool_call_id="provider-tool-1",
            index=0,
            name="number_comparator",
            arguments_delta='2,"right":1}',
        )
        yield ModelToolCallCompleted(
            tool_call=ToolCallItem(
                id="tool-item-1",
                provider_tool_call_id="provider-tool-1",
                index=0,
                status=ToolCallStatus.READY,
                function=ToolFunction(
                    name="number_comparator",
                    arguments_text='{"left":2,"right":1}',
                    arguments_json={"left": 2, "right": 1},
                ),
            ),
        )
        yield ModelStepResult(
            assistant_item=AgentMessageItem(text=""),
            tool_calls=[
                ToolCallItem(
                    id="tool-item-1",
                    provider_tool_call_id="provider-tool-1",
                    index=0,
                    status=ToolCallStatus.READY,
                    function=ToolFunction(
                        name="number_comparator",
                        arguments_text='{"left":2,"right":1}',
                        arguments_json={"left": 2, "right": 1},
                    ),
                ),
            ],
            stop_reason="tool_calls",
        )


@dataclass
class RecordingContextManager:
    """Context manager fake that projects current turn items into envelopes."""

    def build_prompt(
        self,
        *,
        turn: Turn,
        session_items: list[SessionItem],
        tools: list[ToolDefinition],
    ) -> PromptEnvelope:
        """Build a prompt envelope from visible current-turn items."""
        _ = turn
        return PromptEnvelope(
            base_instructions="Base policy",
            current_user_item=UserMessageItem(content=[
                UserInput(type=UserInputType.TEXT,
                          text="Which number is bigger?"),
            ]),
            turn_items=[
                item
                for item in session_items
                if isinstance(item, AgentMessageItem | ReasoningItem | ToolCallItem)
                or (
                    isinstance(item, UserMessageItem)
                    and item.metadata.get("runtime_input") == "steering"
                )
            ],
            tools=tools,
            tool_choice=ToolChoice.AUTO,
        )


class CompletingToolRuntime:
    """Tool runtime fake that completes every requested tool call."""

    def visible_tools(self) -> list[ToolDefinition]:
        """Return no tool schemas because the model client is scripted."""
        return []

    async def execute(self, tool_calls: list[ToolCallItem]) -> list[ToolCallItem]:
        """Return completed versions of requested tool-call items."""
        return [
            call.model_copy(update={
                "status": ToolCallStatus.COMPLETED,
                "result": ToolCallResult(content='{"comparison":"greater"}'),
            })
            for call in tool_calls
        ]


class SteeringControl:
    """Runtime control fake that injects one steering message after tools run."""

    def __init__(self, text: str) -> None:
        """Create the fake control with one steering payload."""
        self._text = text
        self._checks = 0

    async def abort_requested(self) -> bool:
        """Never abort during this steering test."""
        return False

    async def drain_steering(self) -> list[UserMessageItem]:
        """Return one steering item only before the second model sample."""
        self._checks += 1
        if self._checks != 2:
            return []
        return [
            UserMessageItem(content=[
                UserInput(type=UserInputType.TEXT, text=self._text),
            ], metadata={"runtime_input": "steering"})
        ]


class AbortControl:
    """Runtime control fake that requests immediate abort."""

    async def abort_requested(self) -> bool:
        """Request abort before model sampling."""
        return True

    async def drain_steering(self) -> list[UserMessageItem]:
        """Return no steering input."""
        return []


class FailingModelClient:
    """Model client fake that must never be called."""

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Fail if abort does not stop the loop before sampling."""
        _ = envelope
        raise AssertionError("model client should not be sampled")


def _tool_call() -> ToolCallItem:
    """Build a requested number comparison tool call."""
    return ToolCallItem(
        provider_tool_call_id="provider-tool-1",
        function=ToolFunction(
            name="number_comparator",
            arguments_text='{"left":2,"right":1}',
            arguments_json={"left": 2, "right": 1},
        ),
    )
