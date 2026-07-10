"""Tests for the direct Chat Completions model client."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from icore_agent.config import ResolvedLiteLLMConfig
from icore_agent.contexts.agent.domain.loop import (
    ModelReasoningDelta,
    ModelStepResult,
    ModelToolCallCompleted,
    ModelToolCallDelta,
    ModelToolCallStarted,
)
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ReasoningItem,
    ToolCallItem,
    ToolCallStatus,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.tool import ToolChoice, ToolDefinition
from icore_agent.contexts.agent.infrastructure.chat_completions import (
    ChatCompletionsModelClient,
    create_chat_completions_model_client,
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
                    "reasoning_content": "I should compare both numbers.",
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
        "icore_agent.contexts.agent.infrastructure.chat_completions.runner.litellm.acompletion",
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
    assert result.reasoning_item is not None
    assert result.reasoning_item.text == "I should compare both numbers."
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
                    "delta": {"reasoning_content": "Compare "},
                    "finish_reason": None,
                }],
            }
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {"reasoning_content": "the values."},
                    "finish_reason": None,
                }],
            }
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
        "icore_agent.contexts.agent.infrastructure.chat_completions.runner.litellm.acompletion",
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
    assert result.reasoning_item is not None
    assert result.reasoning_item.text == "Compare the values."
    assert result.stop_reason == "stop"
    assert result.usage == {
        "prompt_tokens": 2,
        "completion_tokens": 1,
        "total_tokens": 3,
    }


@pytest.mark.asyncio
async def test_chat_completions_model_client_streams_reasoning_deltas(
    monkeypatch,
) -> None:
    """Model client should expose LiteLLM reasoning_content independently."""

    async def fake_completion(**kwargs: Any) -> Any:
        _ = kwargs

        async def chunks() -> Any:
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {"reasoning_content": "Inspect evidence."},
                    "finish_reason": None,
                }],
            }
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {"content": "Answer"},
                    "finish_reason": "stop",
                }],
            }

        return chunks()

    monkeypatch.setattr(
        "icore_agent.contexts.agent.infrastructure.chat_completions.runner.litellm.acompletion",
        fake_completion,
    )
    client = ChatCompletionsModelClient(
        model_id="test-provider/test-model",
        client_args={},
        params={},
    )

    events = [event async for event in client.stream(_envelope(_tool_definition()))]

    assert [
        event.text
        for event in events
        if isinstance(event, ModelReasoningDelta)
    ] == ["Inspect evidence."]
    final = events[-1]
    assert isinstance(final, ModelStepResult)
    assert final.reasoning_item is not None
    assert final.reasoning_item.text == "Inspect evidence."


@pytest.mark.asyncio
async def test_chat_completions_model_client_streams_tool_call_deltas(
    monkeypatch,
) -> None:
    """Streaming tool-call chunks should be exposed before the final result."""

    async def fake_completion(**kwargs: Any) -> Any:
        async def chunks() -> Any:
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "index": 0,
                            "id": "provider-tool-1",
                            "type": "function",
                            "function": {
                                "name": "number_comparator",
                                "arguments": '{"left":',
                            },
                        }],
                    },
                    "finish_reason": None,
                }],
            }
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "index": 0,
                            "function": {
                                "arguments": '2,"right":1}',
                            },
                        }],
                    },
                    "finish_reason": "tool_calls",
                }],
            }

        return chunks()

    monkeypatch.setattr(
        "icore_agent.contexts.agent.infrastructure.chat_completions.runner.litellm.acompletion",
        fake_completion,
    )
    client = ChatCompletionsModelClient(
        model_id="test-provider/test-model",
        client_args={},
        params={},
    )

    events = [
        event
        async for event in client.stream(_envelope(_tool_definition()))
    ]

    assert isinstance(events[0], ModelToolCallStarted)
    assert events[0].provider_tool_call_id == "provider-tool-1"
    assert events[0].name == "number_comparator"
    assert [
        event.arguments_delta
        for event in events
        if isinstance(event, ModelToolCallDelta)
    ] == ['{"left":', '2,"right":1}']
    completed = next(
        event
        for event in events
        if isinstance(event, ModelToolCallCompleted)
    )
    assert completed.tool_call.provider_tool_call_id == "provider-tool-1"
    assert completed.tool_call.function.arguments_json == {
        "left": 2,
        "right": 1,
    }
    final = events[-1]
    assert isinstance(final, ModelStepResult)
    assert final.tool_calls[0].provider_tool_call_id == "provider-tool-1"
    assert final.stop_reason == "tool_calls"


@pytest.mark.asyncio
async def test_streamed_invalid_tool_arguments_are_not_coerced_to_empty_object(
    monkeypatch,
) -> None:
    """Malformed streamed arguments should finalize as a failed tool call."""

    async def fake_completion(**kwargs: Any) -> Any:
        _ = kwargs

        async def chunks() -> Any:
            yield {
                "id": "response-1",
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "index": 0,
                            "id": "provider-tool-1",
                            "type": "function",
                            "function": {
                                "name": "number_comparator",
                                "arguments": '{"left":',
                            },
                        }],
                    },
                    "finish_reason": "tool_calls",
                }],
            }

        return chunks()

    monkeypatch.setattr(
        "icore_agent.contexts.agent.infrastructure.chat_completions.runner.litellm.acompletion",
        fake_completion,
    )
    client = ChatCompletionsModelClient(
        model_id="test-provider/test-model",
        client_args={},
        params={},
    )

    events = [
        event
        async for event in client.stream(_envelope(_tool_definition()))
    ]

    completed = next(
        event
        for event in events
        if isinstance(event, ModelToolCallCompleted)
    )
    assert completed.tool_call.status == ToolCallStatus.FAILED
    assert completed.tool_call.function.arguments_text == '{"left":'
    assert completed.tool_call.function.arguments_json is None
    assert completed.tool_call.error is not None
    assert completed.tool_call.error.code == "InvalidToolArguments"
    final = events[-1]
    assert isinstance(final, ModelStepResult)
    assert final.tool_calls[0].status == ToolCallStatus.FAILED


@pytest.mark.asyncio
async def test_complete_response_invalid_tool_arguments_use_same_validation(
    monkeypatch,
) -> None:
    """Non-streaming fallbacks should share strict tool argument validation."""

    async def fake_completion(**kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        return {
            "id": "response-1",
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "provider-tool-1",
                        "type": "function",
                        "function": {
                            "name": "number_comparator",
                            "arguments": "[]",
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }

    monkeypatch.setattr(
        "icore_agent.contexts.agent.infrastructure.chat_completions.runner.litellm.acompletion",
        fake_completion,
    )
    client = ChatCompletionsModelClient(
        model_id="test-provider/test-model",
        client_args={},
        params={},
    )

    result = await client.sample(_envelope(_tool_definition()))

    assert result.tool_calls[0].status == ToolCallStatus.FAILED
    assert result.tool_calls[0].function.arguments_text == "[]"
    assert result.tool_calls[0].function.arguments_json is None


def test_create_chat_completions_model_client_uses_resolved_model(
    monkeypatch,
) -> None:
    """Chat Completions client factory should use resolved LiteLLM settings."""
    from icore_agent.contexts.agent.infrastructure.chat_completions import runner

    mock_settings = MagicMock()
    mock_settings.effective_model_id.return_value = "test-model"
    mock_settings.agent_max_tokens = 123
    mock_settings.agent_temperature = 0.2
    mock_settings.resolve_litellm_config.return_value = ResolvedLiteLLMConfig(
        model_id="test-model",
        client_args={"api_key": "secret"},
        params={"max_tokens": 123, "temperature": 0.2},
    )
    monkeypatch.setattr(runner, "settings", mock_settings)

    model_client = create_chat_completions_model_client(
        session_id="session-1",
        user_id="user-1",
    )

    assert isinstance(model_client, ChatCompletionsModelClient)
    mock_settings.resolve_litellm_config.assert_called_once_with(
        model_id="test-model",
        user_id="user-1",
        session_id="session-1",
        max_tokens=123,
        temperature=0.2,
    )


def _envelope(
    tool_definition: ToolDefinition,
    *,
    turn_items: list[AgentMessageItem | ReasoningItem |
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
