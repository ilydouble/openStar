"""Tests for provider-neutral agent prompt envelopes."""

from __future__ import annotations

from icore_agent.domain.agent.prompt import (
    BaseInstructions,
    ContextItem,
    ModelVisibleItem,
    PromptEnvelope,
    ToolChoice,
    ToolSpec,
    UserPromptItem,
)
from icore_agent.infrastructure.agent.chat_completions import (
    render_chat_completions_messages,
    render_chat_completions_tools,
)


def test_prompt_envelope_renders_base_context_history_and_user_in_order() -> None:
    """PromptEnvelope should render base instructions separately from history."""
    envelope = PromptEnvelope(
        base_instructions=BaseInstructions(text="Base policy"),
        context_items=[
            ContextItem(kind="summary", content="Earlier summary"),
            ContextItem(kind="file_attachment", content="file uuid=file-1"),
        ],
        history_items=[
            ModelVisibleItem(role="user", content="Old question"),
            ModelVisibleItem(role="assistant", content="Old answer"),
        ],
        current_user_item=UserPromptItem(content="Current question"),
        tools=[
            ToolSpec(
                name="read_uploaded_file",
                description="Read uploaded files.",
                parameters={"type": "object"},
            )
        ],
        tool_choice=ToolChoice.AUTO,
    )

    messages = render_chat_completions_messages(envelope)

    assert messages == [
        {"role": "system", "content": "Base policy"},
        {"role": "user", "content": "Earlier summary"},
        {"role": "user", "content": "file uuid=file-1"},
        {"role": "user", "content": "Old question"},
        {"role": "assistant", "content": "Old answer"},
        {"role": "user", "content": "Current question"},
    ]
    assert all(message["content"] != "Base policy" for message in messages[1:])


def test_prompt_envelope_renders_tools_as_top_level_schema() -> None:
    """Tool specs should render as Chat Completions tools, not prompt text."""
    envelope = PromptEnvelope(
        base_instructions=BaseInstructions(text="Base policy"),
        context_items=[],
        history_items=[],
        current_user_item=UserPromptItem(content="Current question"),
        tools=[
            ToolSpec(
                name="number_comparator",
                description="Compare numbers.",
                parameters={
                    "type": "object",
                    "properties": {"left": {"type": "number"}},
                },
            )
        ],
        tool_choice=ToolChoice.AUTO,
    )

    assert render_chat_completions_tools(envelope) == [
        {
            "type": "function",
            "function": {
                "name": "number_comparator",
                "description": "Compare numbers.",
                "parameters": {
                    "type": "object",
                    "properties": {"left": {"type": "number"}},
                },
            },
        }
    ]
