"""Assemble provider-neutral prompt envelopes for agent turns."""

from __future__ import annotations

import json
from typing import Any

from icore_agent.domain.agent.prompt import (
    PromptEnvelope,
    build_base_instructions,
)
from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.context import AgentContext
from icore_agent.domain.agent.session import (
    ContextItem,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition


def build_agent_prompt_envelope(
    *,
    command: Any,
    context: AgentContext,
    tool_definitions: list[ToolDefinition],
) -> PromptEnvelope:
    """Build the model-visible prompt envelope for one agent turn."""
    return PromptEnvelope(
        base_instructions=build_base_instructions(),
        context_items=_context_items(context),
        history_items=context.history_items,
        current_user_item=UserMessageItem(
            content=[
                UserInput(
                    type=UserInputType.TEXT,
                    text=command.agent_message or command.message,
                ),
            ],
        ),
        tools=tool_definitions,
        tool_choice=ToolChoice.AUTO,
    )


def _context_items(context: AgentContext) -> list[ContextItem]:
    """Return explicit context items that should be visible to the model."""
    items: list[ContextItem] = []
    if context.summary:
        items.append(ContextItem(
            kind="session_summary",
            role_hint=ChatCompletionRole.USER,
            content=f"Earlier conversation summary:\n{context.summary}",
        ))
    if context.user_memory_prompt:
        items.append(ContextItem(
            kind="user_memory",
            role_hint=ChatCompletionRole.USER,
            content=context.user_memory_prompt,
        ))
    attachment_note = _attachment_reference_note(context)
    if attachment_note:
        items.append(ContextItem(
            kind="attachments",
            role_hint=ChatCompletionRole.USER,
            content=attachment_note,
        ))
    return items


def _attachment_reference_note(context: AgentContext) -> str:
    """Build metadata-only attachment context without inlining file content."""
    image_refs = context.image_attachment_payloads
    file_refs = context.file_attachment_payloads
    if not image_refs and not file_refs:
        return ""

    lines = ["Attached files for this turn:"]
    for attachment in image_refs:
        lines.append(
            "- image_attachment "
            f"filename={_json_value(attachment.get('filename'))} "
            f"uuid={_json_value(attachment.get('file_uuid'))} "
            f"ref={_json_value(attachment.get('ref'))}"
        )
    for attachment in file_refs:
        lines.append(
            "- file_attachment "
            f"filename={_json_value(attachment.get('filename'))} "
            f"uuid={_json_value(attachment.get('file_uuid'))}"
        )
    if file_refs:
        lines.append(
            "Use read_uploaded_file with the uuid when file_attachment "
            "contents are needed."
        )
    return "\n".join(lines)


def _json_value(value: Any) -> str:
    """Render one attachment metadata value as a quoted JSON string."""
    return json.dumps(str(value or ""), ensure_ascii=False)
