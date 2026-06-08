"""Tests for chat turn and session-item domain models."""

from __future__ import annotations

from pydantic import TypeAdapter

from icore_agent.domain.chat.session import (
    AgentMessageItem,
    SessionItem,
    ToolCallItem,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.chat.turn import Turn


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

    assert isinstance(user_item, UserMessageItem)
    assert isinstance(agent_item, AgentMessageItem)
    assert isinstance(tool_item, ToolCallItem)


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
