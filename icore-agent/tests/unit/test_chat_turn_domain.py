"""Tests for chat turn and session-item domain models."""

from __future__ import annotations

from pydantic import TypeAdapter

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    SessionItem,
    SessionItemType,
    ToolCallItem,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.turn import Turn


def test_session_item_union_parses_user_agent_and_tool_items() -> None:
    """SessionItem should parse every first-version timeline item shape."""
    adapter = TypeAdapter(SessionItem)

    user_item = adapter.validate_python({
        "type": "user_message",
        "content": [{"type": "text", "text": "Hello"}],
    })
    agent_item = adapter.validate_python({
        "type": "agent_message",
        "text": "Hi",
    })
    tool_item = adapter.validate_python({
        "type": "tool_call",
        "function": {
            "name": "get_weather",
            "arguments_text": "{\"location\":\"北京\"}",
            "arguments_json": {"location": "北京"},
        },
    })
    context_item = adapter.validate_python({
        "type": "context",
        "kind": "session_summary",
        "role_hint": ChatCompletionRole.USER.value,
        "content": "当前会话摘要：用户正在设计销售数据分析模块。",
    })

    assert isinstance(user_item, UserMessageItem)
    assert isinstance(agent_item, AgentMessageItem)
    assert isinstance(tool_item, ToolCallItem)
    assert isinstance(context_item, ContextItem)
    assert user_item.type == SessionItemType.USER_MESSAGE.value
    assert agent_item.type == SessionItemType.AGENT_MESSAGE.value
    assert tool_item.type == SessionItemType.TOOL_CALL.value
    assert context_item.type == SessionItemType.CONTEXT.value
    assert context_item.role_hint == ChatCompletionRole.USER.value


def test_turn_upsert_item_replaces_existing_item_by_id() -> None:
    """Turn items should be stable by item id so deltas can update state."""
    turn = Turn(session_id="session-1")
    item = AgentMessageItem(id="item-1", text="")
    completed = AgentMessageItem(id="item-1", text="done")

    turn.upsert_item(UserMessageItem(
        id="user-item-1",
        content=[UserInput(type=UserInputType.TEXT, text="Hello")],
    ))
    turn.upsert_item(item)
    turn.upsert_item(ToolCallItem(
        id="tool-item-1",
        function=ToolFunction(name="search"),
    ))
    turn.upsert_item(completed)

    assert [session_item.id for session_item in turn.items] == [
        "user-item-1",
        "item-1",
        "tool-item-1",
    ]
    assert turn.items[1] == completed


def test_turn_reply_text_returns_last_agent_message() -> None:
    """Turn should expose final assistant text without a duplicate reply field."""
    turn = Turn(session_id="session-1")

    assert turn.reply_text() == ""

    turn.upsert_item(AgentMessageItem(id="agent-1", text="first"))
    turn.upsert_item(ToolCallItem(
        id="tool-item-1",
        function=ToolFunction(name="search"),
    ))
    turn.upsert_item(AgentMessageItem(id="agent-2", text="final"))

    assert turn.reply_text() == "final"
