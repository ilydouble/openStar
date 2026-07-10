"""Tests for chat turn and session-item domain models."""

from __future__ import annotations

from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ToolCallItem,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.turn import Turn


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
