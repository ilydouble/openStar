"""Tests for application-level agent tool execution runtime."""

from __future__ import annotations

from typing import Any

import pytest

from icore_agent.contexts.agent.application.tool.runtime import ToolRuntime
from icore_agent.contexts.agent.domain.session import (
    ToolCallItem,
    ToolCallStatus,
    ToolFunction,
)
from icore_agent.contexts.agent.domain.tool import (
    ToolDefinition,
    ToolExecutionContext,
)


@pytest.mark.asyncio
async def test_tool_runtime_executes_tool_call_and_returns_completed_item() -> None:
    """ToolRuntime should execute known tools and return completed tool items."""
    runtime = ToolRuntime([_tool_definition()])
    call = _tool_call(arguments={"left": 2, "right": 1})

    results = await runtime.execute([call])

    assert len(results) == 1
    assert results[0].id == call.id
    assert results[0].status is ToolCallStatus.COMPLETED
    assert results[0].result.content == '{"comparison":"greater"}'
    assert results[0].result.structured_content == {
        "comparison": "greater",
    }
    assert results[0].error is None


@pytest.mark.asyncio
async def test_tool_runtime_returns_failed_item_for_unknown_tool() -> None:
    """Unknown tool names should become failed ToolCallItems visible to the model."""
    runtime = ToolRuntime([])
    call = _tool_call(name="missing_tool")

    results = await runtime.execute([call])

    assert results[0].status is ToolCallStatus.FAILED
    assert results[0].error.message == "Unknown tool: missing_tool"
    assert results[0].result.content == "Unknown tool: missing_tool"


@pytest.mark.asyncio
async def test_tool_runtime_returns_failed_item_for_tool_exception() -> None:
    """Tool exceptions should be represented as failed tool result items."""
    runtime = ToolRuntime([_tool_definition(raise_error=True)])
    call = _tool_call(arguments={"left": 2, "right": 1})

    results = await runtime.execute([call])

    assert results[0].status is ToolCallStatus.FAILED
    assert results[0].error.code == "ValueError"
    assert results[0].result.content == "tool exploded"


def _tool_definition(*, raise_error: bool = False) -> ToolDefinition:
    """Build a tool definition for runtime execution tests."""

    def _execute(
        tool_call_id: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, str]:
        """Compare two numbers or raise a controlled exception."""
        assert tool_call_id == "provider-tool-1"
        assert context.tool_call_id == "provider-tool-1"
        if raise_error:
            raise ValueError("tool exploded")
        return {
            "comparison": (
                "greater" if params["left"] > params["right"] else "other"
            ),
        }

    return ToolDefinition(
        name="number_comparator",
        label="Number comparator",
        description="Compare numbers.",
        parameters={"type": "object"},
        execute=_execute,
    )


def _tool_call(
    *,
    name: str = "number_comparator",
    arguments: dict[str, Any] | None = None,
) -> ToolCallItem:
    """Build a requested tool-call item for runtime tests."""
    return ToolCallItem(
        provider_tool_call_id="provider-tool-1",
        function=ToolFunction(
            name=name,
            arguments_text='{"left":2,"right":1}',
            arguments_json=dict(arguments or {"left": 2, "right": 1}),
        ),
    )
