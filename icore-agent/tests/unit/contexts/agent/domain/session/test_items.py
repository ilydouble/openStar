"""Tests for agent session item domain models."""

from pydantic import TypeAdapter

from icore_agent.contexts.agent.domain import ChatCompletionRole
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ContextItem,
    SessionItem,
    SessionItemType,
    ToolCallItem,
    UserInput,
    UserInputType,
    UserMessageItem,
)


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


def test_user_message_item_converts_text_blocks_to_text() -> None:
    """UserMessageItem should own its model-visible text conversion."""
    item = UserMessageItem(content=[
        UserInput(type=UserInputType.TEXT, text="Line one"),
        UserInput(type=UserInputType.IMAGE, image_file_uuid="image-1"),
        UserInput(type=UserInputType.TEXT, text="Line two"),
    ])

    assert item.to_text() == "Line one\nLine two"
