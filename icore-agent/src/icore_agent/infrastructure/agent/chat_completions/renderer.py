"""Render provider-neutral prompt envelopes to Chat Completions payloads."""

from __future__ import annotations

from typing import Any

from icore_agent.domain.agent.prompt import PromptEnvelope, ToolChoice


def render_chat_completions_messages(
    envelope: PromptEnvelope,
) -> list[dict[str, Any]]:
    """Render envelope instructions, context, history, and user input as messages."""
    messages: list[dict[str, Any]] = [{
        "role": "system",
        "content": envelope.base_instructions.text,
    }]
    messages.extend(
        {"role": item.role, "content": item.content}
        for item in envelope.context_items
        if item.content
    )
    messages.extend(
        {"role": item.role, "content": item.content}
        for item in envelope.history_items
        if item.content
    )
    messages.append({
        "role": "user",
        "content": envelope.current_user_item.content,
    })
    return messages


def render_chat_completions_tools(
    envelope: PromptEnvelope,
) -> list[dict[str, Any]]:
    """Render envelope tool specs as top-level Chat Completions tools."""
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
