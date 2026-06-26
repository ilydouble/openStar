"""Tests for AgentLoop helper modules."""

from __future__ import annotations

from typing import Any

from icore_agent.application.agent.async_bridge import patch_runner_callback
from icore_agent.infrastructure.agent.strands import StrandsToolEventBridge
from icore_agent.infrastructure.agent.strands.callback_context import (
    sub_agent_callback,
    set_parent_callback,
    reset_parent_callback,
)
from icore_agent.infrastructure.agent.strands.payloads import (
    json_dumps,
    json_safe_object,
    result_text,
    tool_arguments,
    tool_call_id,
    tool_name,
)
from icore_agent.domain.agent.session import ToolCallItem, ToolCallStatus
from icore_agent.domain.agent.turn import TurnEventKind


def test_tool_payload_helpers_normalize_strands_payloads() -> None:
    """Tool payload helpers should keep Strands parsing outside AgentLoop."""
    tool_use = {
        "toolUseId": "tool-1",
        "name": "web_search",
        "input": {"query": "weather"},
    }
    result = {
        "status": "success",
        "content": [{"text": "ok"}],
    }

    assert tool_call_id(tool_use) == "tool-1"
    assert tool_name(tool_use) == "web_search"
    assert tool_arguments(tool_use) == {"query": "weather"}
    assert json_safe_object(["a"]) == {"value": ["a"]}
    assert json_dumps({"城市": "北京"}) == '{"城市":"北京"}'
    assert result_text(result) == "ok"


def test_strands_tool_event_bridge_emits_tool_start_and_completion() -> None:
    """Strands bridge should emit tool item events without AgentLoop help."""
    bridge = StrandsToolEventBridge(session_id="session-1", turn_id="turn-1")
    events = []

    with bridge.bound_to(
        emit=events.append,
        emit_assistant_delta=lambda token: None,
    ):
        bridge.record_start({
            "toolUseId": "tool-1",
            "name": "web_search",
            "input": {"query": "weather"},
        })
        bridge.record_finish(
            {
                "toolUseId": "tool-1",
                "name": "web_search",
                "input": {"query": "weather"},
            },
            {
                "status": "success",
                "content": [{"text": "ok"}],
            },
            exception=None,
        )

    assert [event.kind for event in events] == [
        TurnEventKind.ITEM_STARTED,
        TurnEventKind.ITEM_COMPLETED,
    ]
    assert isinstance(events[0].item, ToolCallItem)
    assert events[0].item.function.name == "web_search"
    assert events[1].item.status == ToolCallStatus.COMPLETED
    assert events[1].item.result.content == "ok"


def test_strands_tool_event_bridge_forwards_assistant_delta() -> None:
    """Callback token forwarding should live in the Strands bridge."""
    bridge = StrandsToolEventBridge(session_id="session-1", turn_id="turn-1")
    deltas: list[str] = []

    with bridge.bound_to(
        emit=lambda event: None,
        emit_assistant_delta=deltas.append,
    ):
        bridge.on_callback(data="Hi")

    assert deltas == ["Hi"]


def test_patch_runner_callback_restores_fake_runner_callback() -> None:
    """Callback patching should be isolated to async bridge helpers."""
    calls: list[dict[str, Any]] = []

    def previous_callback(**kwargs: Any) -> None:
        calls.append({"previous": kwargs})

    def next_callback(**kwargs: Any) -> None:
        calls.append({"next": kwargs})

    class Runner:
        def __init__(self) -> None:
            self.callback_handler = previous_callback

    runner = Runner()
    with patch_runner_callback(runner, next_callback):
        runner.callback_handler(data="new")

    runner.callback_handler(data="old")

    assert calls == [
        {"next": {"data": "new"}},
        {"previous": {"data": "old"}},
    ]


def test_sub_agent_callback_forwards_only_tool_use_events() -> None:
    """Sub-agent callback context should forward tool calls without token deltas."""
    forwarded: list[dict[str, Any]] = []
    token = set_parent_callback(lambda **kwargs: forwarded.append(kwargs))
    try:
        callback = sub_agent_callback()
        assert callback is not None

        callback(current_tool_use={"toolUseId": "tool-1"})
        callback(data="hidden token")
    finally:
        reset_parent_callback(token)

    assert forwarded == [{"current_tool_use": {"toolUseId": "tool-1"}}]
