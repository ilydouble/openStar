"""Render provider-neutral prompt envelopes to Chat Completions payloads."""

from __future__ import annotations

from html import escape
from typing import Any

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.prompt import (
    PromptEnvelope,
    PromptHistoryItem,
)
from domain.agent.session import AgentMessageItem, ContextItem
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
        "content": envelope.current_user_item.to_text(),
    })
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


def _history_item_text(item: PromptHistoryItem) -> str:
    """Return text used to decide whether a history item is model-visible."""
    if isinstance(item, AgentMessageItem):
        return item.text
    return item.to_text()


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
