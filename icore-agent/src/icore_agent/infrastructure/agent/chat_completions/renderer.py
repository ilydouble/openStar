"""Render provider-neutral prompt envelopes to Chat Completions payloads."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.prompt import (
    PromptEnvelope,
    PromptHistoryItem,
)
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    ToolCallItem,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice


def render_chat_completions_messages(
    envelope: PromptEnvelope,
) -> list[dict[str, Any]]:
    """Render envelope instructions, context, history, and user input as messages."""
    messages: list[dict[str, Any]] = [{
        "role": ChatCompletionRole.SYSTEM.value,
        "content": envelope.base_instructions,
    }]
    messages.extend(
        {
            "role": ChatCompletionRole.USER.value,
            "content": render_context_item(item),
        }
        for item in envelope.context_items
        if item.content
    )
    messages.extend(
        _render_history_message(item)
        for item in envelope.history_items
        if _history_item_text(item)
    )
    messages.append({
        "role": ChatCompletionRole.USER.value,
        "content": _render_current_user_content(envelope.current_user_item),
    })
    messages.extend(_render_turn_messages(envelope.turn_items))
    return messages


def render_context_item(item: ContextItem) -> str:
    """Render one runtime context item as a guarded model-visible block."""
    return (
        f"<context type='{escape(item.kind, quote=True)}'>"
        f"{escape(item.content, quote=True)}</context>"
    )


def _render_history_message(item: PromptHistoryItem) -> dict[str, Any]:
    """Render one prior user or assistant item as a Chat Completions message."""
    if isinstance(item, AgentMessageItem):
        return {"role": ChatCompletionRole.ASSISTANT.value, "content": item.text}
    return {
        "role": ChatCompletionRole.USER.value,
        "content": item.to_text(),
    }


def _render_current_user_content(item: Any) -> str | list[dict[str, Any]]:
    """Render the current user item as text or multimodal Chat Completions content."""
    blocks: list[dict[str, Any]] = []
    has_image = False
    for block in item.content:
        if block.text:
            blocks.append({"type": "text", "text": block.text})
        if block.image_url:
            has_image = True
            blocks.append({
                "type": "image_url",
                "image_url": {"url": block.image_url},
            })
    if has_image:
        return blocks
    return item.to_text()


def _history_item_text(item: PromptHistoryItem) -> str:
    """Return text used to decide whether a history item is model-visible."""
    if isinstance(item, AgentMessageItem):
        return item.text
    return item.to_text()


def _render_turn_messages(
    items: list[AgentMessageItem | ToolCallItem | UserMessageItem],
) -> list[dict[str, Any]]:
    """Render current-turn assistant/tool state for a follow-up model step."""
    messages: list[dict[str, Any]] = []
    index = 0
    while index < len(items):
        item = items[index]
        if isinstance(item, AgentMessageItem):
            tool_calls, next_index = _following_tool_calls(items, index + 1)
            if tool_calls:
                messages.append(_assistant_tool_call_message(item, tool_calls))
                messages.extend(
                    _tool_result_message(tool_call)
                    for tool_call in tool_calls
                    if _tool_result_content(tool_call) is not None
                )
                index = next_index
                continue
            if item.text:
                messages.append({
                    "role": ChatCompletionRole.ASSISTANT.value,
                    "content": item.text,
                })
        elif isinstance(item, UserMessageItem):
            content = _render_current_user_content(item)
            if content:
                messages.append({
                    "role": ChatCompletionRole.USER.value,
                    "content": content,
                })
        elif _tool_result_content(item) is not None:
            messages.append(_tool_result_message(item))
        index += 1
    return messages


def _following_tool_calls(
    items: list[AgentMessageItem | ToolCallItem | UserMessageItem],
    start: int,
) -> tuple[list[ToolCallItem], int]:
    """Return tool calls immediately following an assistant item."""
    tool_calls: list[ToolCallItem] = []
    index = start
    while index < len(items) and isinstance(items[index], ToolCallItem):
        tool_calls.append(items[index])
        index += 1
    return tool_calls, index


def _assistant_tool_call_message(
    assistant: AgentMessageItem,
    tool_calls: list[ToolCallItem],
) -> dict[str, Any]:
    """Render an assistant message that requested tool calls."""
    return {
        "role": ChatCompletionRole.ASSISTANT.value,
        "content": assistant.text or None,
        "tool_calls": [
            {
                "id": _provider_tool_call_id(tool_call),
                "type": "function",
                "function": {
                    "name": tool_call.function.name or "",
                    "arguments": _tool_arguments_text(tool_call),
                },
            }
            for tool_call in tool_calls
        ],
    }


def _tool_result_message(tool_call: ToolCallItem) -> dict[str, Any]:
    """Render one completed or failed tool call as a tool-role message."""
    return {
        "role": ChatCompletionRole.TOOL.value,
        "tool_call_id": _provider_tool_call_id(tool_call),
        "name": tool_call.function.name or "",
        "content": _tool_result_content(tool_call) or "",
    }


def _provider_tool_call_id(tool_call: ToolCallItem) -> str:
    """Return the provider tool-call id used by Chat Completions."""
    return tool_call.provider_tool_call_id or tool_call.id


def _tool_arguments_text(tool_call: ToolCallItem) -> str:
    """Return function-call arguments text for Chat Completions replay."""
    if tool_call.function.arguments_text:
        return tool_call.function.arguments_text
    return json.dumps(
        tool_call.function.arguments_json or {},
        ensure_ascii=False,
    )


def _tool_result_content(tool_call: ToolCallItem) -> str | None:
    """Return model-visible tool output or error text."""
    if tool_call.result and tool_call.result.content is not None:
        return tool_call.result.content
    if tool_call.error is not None:
        return tool_call.error.message
    return None


def render_chat_completions_tools(
    envelope: PromptEnvelope,
) -> list[dict[str, Any]]:
    """Render envelope tool definitions as top-level Chat Completions tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in envelope.tools
    ]


def render_chat_completions_tool_choice(envelope: PromptEnvelope) -> str:
    """Render provider-neutral tool choice for Chat Completions."""
    choice = envelope.tool_choice
    if isinstance(choice, ToolChoice):
        return choice.value
    return str(choice)
