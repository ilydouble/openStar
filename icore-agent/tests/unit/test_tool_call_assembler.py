"""Tests for streamed tool-call assembly and argument validation."""

from __future__ import annotations

import pytest

from icore_agent.contexts.agent.domain.loop import (
    ModelToolCallDelta,
    ModelToolCallStarted,
)
from icore_agent.contexts.agent.domain.session import ToolCallStatus
from icore_agent.contexts.agent.infrastructure.chat_completions.tool_call_assembler import (
    ToolCallAssembler,
    ToolCallChunk,
)


def test_assembler_merges_fragments_and_late_provider_metadata() -> None:
    """One stable item should accumulate arguments and late provider fields."""
    assembler = ToolCallAssembler()

    first_events = assembler.consume(ToolCallChunk(
        index=0,
        arguments_delta='{"left":',
    ))
    second_events = assembler.consume(ToolCallChunk(
        index=0,
        provider_tool_call_id="provider-tool-1",
        name="number_comparator",
        arguments_delta='2,"right":1}',
    ))
    empty_events = assembler.consume(ToolCallChunk(
        index=0,
        arguments_delta="",
    ))
    calls = assembler.finalize(finish_reason="tool_calls")

    assert isinstance(first_events[0], ModelToolCallStarted)
    assert isinstance(first_events[1], ModelToolCallDelta)
    assert second_events[0].item_id == first_events[0].item_id
    assert second_events[0].provider_tool_call_id == "provider-tool-1"
    assert second_events[0].name == "number_comparator"
    assert empty_events == []
    assert len(calls) == 1
    assert calls[0].id == first_events[0].item_id
    assert calls[0].status == ToolCallStatus.READY
    assert calls[0].function.arguments_text == '{"left":2,"right":1}'
    assert calls[0].function.arguments_json == {"left": 2, "right": 1}


def test_assembler_keeps_parallel_calls_isolated_and_ordered() -> None:
    """Parallel tool calls should be finalized independently by index."""
    assembler = ToolCallAssembler()
    assembler.consume(ToolCallChunk(
        index=1,
        provider_tool_call_id="tool-2",
        name="second",
        arguments_delta='{"value":2}',
    ))
    assembler.consume(ToolCallChunk(
        index=0,
        provider_tool_call_id="tool-1",
        name="first",
        arguments_delta='{"value":1}',
    ))

    calls = assembler.finalize(finish_reason="tool_calls")

    assert [call.index for call in calls] == [0, 1]
    assert [call.function.arguments_json for call in calls] == [
        {"value": 1},
        {"value": 2},
    ]


@pytest.mark.parametrize(
    ("arguments", "finish_reason", "message_fragment"),
    [
        ("", "tool_calls", "were empty"),
        ('{"left":', "tool_calls", "not valid JSON"),
        ("[]", "tool_calls", "must be a JSON object"),
        ("42", "tool_calls", "must be a JSON object"),
        ('{"left":2}', "length", "stopped with 'length'"),
    ],
)
def test_assembler_rejects_unsafe_tool_arguments(
    arguments: str,
    finish_reason: str,
    message_fragment: str,
) -> None:
    """Unsafe arguments should become failed calls instead of empty objects."""
    assembler = ToolCallAssembler()
    assembler.consume(ToolCallChunk(
        index=0,
        provider_tool_call_id="provider-tool-1",
        name="number_comparator",
        arguments_delta=arguments,
    ))

    call = assembler.finalize(finish_reason=finish_reason)[0]

    assert call.status == ToolCallStatus.FAILED
    assert call.function.arguments_text == arguments
    assert call.function.arguments_json is None
    assert call.error is not None
    assert call.error.code == "InvalidToolArguments"
    assert message_fragment in call.error.message
    assert call.result is not None
    assert call.result.content == call.error.message
