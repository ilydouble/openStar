"""Tests for the application-owned agent model/tool loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from icore_agent.application.agent.loop import (
    AgentLoop,
    AgentLoopError,
    AgentLoopRequest,
    ModelStepResult,
)
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    SessionItem,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition
from icore_agent.domain.agent.turn import Turn, TurnEventKind


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
        TurnEventKind.ITEM_COMPLETED,
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_COMPLETED,
    ]
    assert model_client.prompt_turn_item_types == [
        [],
        ["agent_message", "tool_call"],
    ]
    assert turn.reply_text() == "2 is greater than 1."


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
                if isinstance(item, AgentMessageItem | ToolCallItem)
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
