"""Tests for the direct Chat Completions agent runner."""

from __future__ import annotations

from typing import Any

from icore_agent.application.agent.tool import ToolDefinition, ToolExecutionContext
from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.session import UserInput, UserInputType, UserMessageItem
from icore_agent.domain.agent.prompt import (
    PromptEnvelope,
    ToolChoice,
    ToolSpec,
)
from icore_agent.infrastructure.agent.chat_completions import (
    ChatCompletionsRunner,
    ChatCompletionsToolEventBridge,
)


def test_chat_completions_runner_executes_tool_call_and_continues(monkeypatch) -> None:
    """Runner should execute model-requested tools and continue to a final answer."""
    calls: list[dict[str, Any]] = []

    def fake_completion(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "choices": [{
                    "message": {
                        "content": None,
                        "tool_calls": [{
                            "id": "tool-1",
                            "type": "function",
                            "function": {
                                "name": "number_comparator",
                                "arguments": '{"left": 2, "right": 1}',
                            },
                        }],
                    }
                }],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        return {
            "choices": [{
                "message": {"content": "2 is greater than 1."}
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(
        "icore_agent.infrastructure.agent.chat_completions.runner.litellm.completion",
        fake_completion,
    )
    bridge = RecordingToolBridge()
    runner = ChatCompletionsRunner(
        model_id="test-model",
        client_args={},
        params={},
        tool_definitions=[
            ToolDefinition(
                name="number_comparator",
                label="Number comparator",
                description="Compare numbers.",
                parameters={"type": "object"},
                execute=_compare_numbers,
            )
        ],
        tool_bridge=bridge,
    )
    envelope = PromptEnvelope(
        base_instructions="Base policy",
        context_items=[],
        history_items=[],
        current_user_item=UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="Which is larger?"),
        ]),
        tools=[
            ToolSpec(
                name="number_comparator",
                description="Compare numbers.",
                parameters={"type": "object"},
            )
        ],
        tool_choice=ToolChoice.AUTO,
    )

    reply = runner(envelope)

    assert reply == "2 is greater than 1."
    assert calls[0]["tools"][0]["function"]["name"] == "number_comparator"
    assert calls[0]["tool_choice"] == "auto"
    assert calls[1]["messages"][-1] == {
        "role": ChatCompletionRole.TOOL.value,
        "tool_call_id": "tool-1",
        "name": "number_comparator",
        "content": '{"comparison": "greater"}',
    }
    assert bridge.started == [{
        "toolUseId": "tool-1",
        "name": "number_comparator",
        "input": {"left": 2, "right": 1},
    }]
    assert bridge.finished[0][1]["status"] == "success"


def test_chat_completions_tool_event_bridge_emits_turn_events() -> None:
    """Tool event bridge should convert direct tool payloads into turn events."""
    bridge = ChatCompletionsToolEventBridge(
        session_id="session-1",
        turn_id="turn-1",
    )
    events: list[Any] = []

    with bridge.bound_to(
        emit=events.append,
        emit_assistant_delta=lambda _token: None,
    ):
        tool_use = {
            "toolUseId": "tool-1",
            "name": "number_comparator",
            "input": {"left": 2, "right": 1},
        }
        bridge.record_start(tool_use)
        bridge.record_finish(
            tool_use,
            {
                "toolUseId": "tool-1",
                "status": "success",
                "content": [{"text": '{"comparison":"greater"}'}],
            },
            exception=None,
        )

    assert len(events) == 2
    assert events[0].turn_id == "turn-1"
    assert events[0].item.provider_tool_call_id == "tool-1"
    assert events[0].item.function.name == "number_comparator"
    assert events[1].item.result.content == '{"comparison":"greater"}'


def _compare_numbers(
    _tool_call_id: str,
    params: dict[str, Any],
    _context: ToolExecutionContext,
) -> dict[str, str]:
    """Return a deterministic comparison result."""
    return {"comparison": "greater" if params["left"] > params["right"] else "other"}


class RecordingToolBridge:
    """Tool bridge fake that records normalized tool events."""

    def __init__(self) -> None:
        """Create the fake bridge."""
        self.started: list[dict[str, Any]] = []
        self.finished: list[tuple[dict[str, Any],
                                  dict[str, Any], Exception | None]] = []

    def record_start(self, tool_use: dict[str, Any]) -> None:
        """Record one tool start."""
        self.started.append(tool_use)

    def record_finish(
        self,
        tool_use: dict[str, Any],
        result: dict[str, Any],
        *,
        exception: Exception | None,
    ) -> None:
        """Record one tool completion."""
        self.finished.append((tool_use, result, exception))
