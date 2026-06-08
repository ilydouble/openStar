"""Tests for structured agent tool definitions."""

from __future__ import annotations

from typing import Any

import pytest

from icore_agent.application.agent.tool import (
    AgentTool,
    ToolDefinition,
    ToolExecutionContext,
)


@pytest.mark.asyncio
async def test_agent_tool_exposes_spec_and_streams_success() -> None:
    """AgentTool should adapt ToolDefinition into a Strands tool result."""
    calls: list[tuple[str, dict[str, Any], ToolExecutionContext]] = []

    def _execute(
        tool_call_id: str,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """Record invocation details and return structured data."""
        calls.append((tool_call_id, params, context))
        return {"echo": params["value"]}

    tool = AgentTool(ToolDefinition(
        name="echo_tool",
        label="Echo tool",
        description="Echo a value.",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        execute=_execute,
        prompt_snippet="Echo a value.",
    ))

    events = []
    async for event in tool.stream(
        {"toolUseId": "call-1", "name": "echo_tool", "input": {"value": "ok"}},
        {"session_id": "session-1"},
    ):
        events.append(event)

    assert tool.tool_name == "echo_tool"
    assert tool.tool_type == "python"
    assert tool.tool_spec["name"] == "echo_tool"
    assert tool.tool_spec["inputSchema"]["json"]["required"] == ["value"]
    assert calls[0][0] == "call-1"
    assert calls[0][1] == {"value": "ok"}
    assert calls[0][2].invocation_state["session_id"] == "session-1"
    assert events[0]["type"] == "tool_result"
    assert events[0]["tool_result"]["status"] == "success"
    assert events[0]["tool_result"]["content"][0]["text"] == '{"echo": "ok"}'


@pytest.mark.asyncio
async def test_agent_tool_streams_error_result_on_exception() -> None:
    """AgentTool should convert executor exceptions into error results."""

    def _execute(
        _tool_call_id: str,
        _params: dict[str, Any],
        _context: ToolExecutionContext,
    ) -> str:
        """Raise a stable test exception."""
        raise RuntimeError("boom")

    tool = AgentTool(ToolDefinition(
        name="failing_tool",
        label="Failing tool",
        description="Always fails.",
        parameters={"type": "object"},
        execute=_execute,
    ))

    events = []
    async for event in tool.stream(
        {"toolUseId": "call-2", "name": "failing_tool", "input": {}},
        {},
    ):
        events.append(event)

    assert events[0]["tool_result"]["toolUseId"] == "call-2"
    assert events[0]["tool_result"]["status"] == "error"
    assert events[0]["tool_result"]["content"][0]["text"] == "boom"
    assert isinstance(events[0].exception, RuntimeError)
