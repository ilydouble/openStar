"""Tests for the direct Chat Completions model client."""

from __future__ import annotations

from typing import Any

import pytest

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition
from icore_agent.infrastructure.agent.chat_completions import (
    ChatCompletionsModelClient,
    render_chat_completions_messages,
)


@pytest.mark.asyncio
async def test_chat_completions_model_client_samples_once_without_running_tools(
    monkeypatch,
) -> None:
    """Model client should return assistant/tool-call items from one provider call."""
    calls: list[dict[str, Any]] = []

    async def fake_completion(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "id": "response-1",
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
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }

    monkeypatch.setattr(
        "icore_agent.infrastructure.agent.chat_completions.runner.litellm.acompletion",
        fake_completion,
    )
    tool_definition = _tool_definition()
    client = ChatCompletionsModelClient(
        model_id="test-provider/test-model",
        client_args={},
        params={},
    )

    result = await client.sample(_envelope(tool_definition))

    assert len(calls) == 1
    assert calls[0]["tools"][0]["function"]["name"] == "number_comparator"
    assert calls[0]["tool_choice"] == "auto"
    assert result.assistant_item.text == ""
    assert result.stop_reason == "tool_calls"
    assert result.model == "test-provider/test-model"
    assert result.provider == "test-provider"
    assert result.usage == {
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
    }
    assert [call.provider_tool_call_id for call in result.tool_calls] == [
        "tool-1",
    ]
    assert result.tool_calls[0].function.name == "number_comparator"
    assert result.tool_calls[0].function.arguments_json == {
        "left": 2,
        "right": 1,
    }


@pytest.mark.asyncio
async def test_chat_completions_model_client_collects_streaming_deltas(
    monkeypatch,
) -> None:
    """Model client should request LiteLLM streaming and expose text deltas."""
    calls: list[dict[str, Any]] = []

    async def fake_completion(**kwargs: Any) -> Any:
        calls.append(kwargs)

        async def chunks() -> Any:
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {"content": "Hel"},
                    "finish_reason": None,
                }],
            }
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {"content": "lo"},
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_tokens": 3,
                },
            }

        return chunks()

    monkeypatch.setattr(
        "icore_agent.infrastructure.agent.chat_completions.runner.litellm.acompletion",
        fake_completion,
    )
    client = ChatCompletionsModelClient(
        model_id="test-provider/test-model",
        client_args={},
        params={},
    )

    result = await client.sample(_envelope(_tool_definition()))

    assert calls[0]["stream"] is True
    assert result.deltas == ["Hel", "lo"]
    assert result.assistant_item.text == "Hello"
    assert result.stop_reason == "stop"
    assert result.usage == {
        "prompt_tokens": 2,
        "completion_tokens": 1,
        "total_tokens": 3,
    }


def test_chat_completions_renderer_projects_turn_tool_state_to_messages() -> None:
    """Renderer should convert current-turn tool state only at the provider boundary."""
    tool_definition = _tool_definition()
    tool_call = ToolCallItem(
        provider_tool_call_id="tool-1",
        function=ToolFunction(
            name="number_comparator",
            arguments_text='{"left":2,"right":1}',
            arguments_json={"left": 2, "right": 1},
        ),
        status=ToolCallStatus.COMPLETED,
        result=ToolCallResult(content='{"comparison":"greater"}'),
    )
    envelope = _envelope(
        tool_definition,
        turn_items=[
            AgentMessageItem(text=""),
            tool_call,
        ],
    )

    messages = render_chat_completions_messages(envelope)

    assert messages[-2] == {
        "role": ChatCompletionRole.ASSISTANT.value,
        "content": None,
        "tool_calls": [{
            "id": "tool-1",
            "type": "function",
            "function": {
                "name": "number_comparator",
                "arguments": '{"left":2,"right":1}',
            },
        }],
    }
    assert messages[-1] == {
        "role": ChatCompletionRole.TOOL.value,
        "tool_call_id": "tool-1",
        "name": "number_comparator",
        "content": '{"comparison":"greater"}',
    }


def test_chat_completions_renderer_projects_turn_user_items_to_messages() -> None:
    """Renderer should expose runtime steering as current-turn user messages."""
    envelope = _envelope(
        _tool_definition(),
        turn_items=[
            AgentMessageItem(text="I will inspect that."),
            UserMessageItem(content=[
                UserInput(
                    type=UserInputType.TEXT,
                    text="Actually avoid network access.",
                ),
            ]),
        ],
    )

    messages = render_chat_completions_messages(envelope)

    assert messages[-2] == {
        "role": ChatCompletionRole.ASSISTANT.value,
        "content": "I will inspect that.",
    }
    assert messages[-1] == {
        "role": ChatCompletionRole.USER.value,
        "content": "Actually avoid network access.",
    }


def _envelope(
    tool_definition: ToolDefinition,
    *,
    turn_items: list[AgentMessageItem |
                     ToolCallItem | UserMessageItem] | None = None,
) -> PromptEnvelope:
    """Build a prompt envelope for chat completions model-client tests."""
    return PromptEnvelope(
        base_instructions="Base policy",
        context_items=[],
        history_items=[],
        current_user_item=UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="Which is larger?"),
        ]),
        turn_items=list(turn_items or []),
        tools=[tool_definition],
        tool_choice=ToolChoice.AUTO,
    )


def _tool_definition() -> ToolDefinition:
    """Return a deterministic number-comparator tool definition."""
    return ToolDefinition(
        name="number_comparator",
        label="Number comparator",
        description="Compare numbers.",
        parameters={"type": "object"},
        execute=_compare_numbers,
    )


def _compare_numbers(*_: Any) -> dict[str, str]:
    """Return a deterministic comparison result."""
    return {"comparison": "greater"}
