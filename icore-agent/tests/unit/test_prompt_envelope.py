"""Tests for provider-neutral agent prompt envelopes."""

from __future__ import annotations

from icore_agent.domain.agent import ChatCompletionRole
from domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition
from icore_agent.infrastructure.agent.chat_completions import (
    render_chat_completions_messages,
    render_chat_completions_tools,
)


def _execute_tool(*_: object) -> str:
    """Return a stable test result for ToolDefinition construction."""
    return "ok"


def test_user_message_item_converts_text_blocks_to_text() -> None:
    """UserMessageItem should own its model-visible text conversion."""
    item = UserMessageItem(content=[
        UserInput(type=UserInputType.TEXT, text="Line one"),
        UserInput(type=UserInputType.IMAGE, image_file_uuid="image-1"),
        UserInput(type=UserInputType.TEXT, text="Line two"),
    ])

    assert item.to_text() == "Line one\nLine two"


def test_prompt_envelope_renders_base_context_history_and_user_in_order() -> None:
    """PromptEnvelope should render base instructions separately from history."""
    envelope = PromptEnvelope(
        base_instructions="Base policy",
        context_items=[
            ContextItem(kind="session_summary", content="Earlier summary"),
            ContextItem(kind="file_attachment", content="file uuid=file-1"),
        ],
        history_items=[
            UserMessageItem(content=[
                UserInput(type=UserInputType.TEXT, text="Old question"),
            ]),
            AgentMessageItem(text="Old answer"),
        ],
        current_user_item=UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="Current question"),
        ]),
        tools=[
            ToolDefinition(
                name="read_uploaded_file",
                label="Read uploaded file",
                description="Read uploaded files.",
                parameters={"type": "object"},
                execute=_execute_tool,
            )
        ],
        tool_choice=ToolChoice.AUTO,
    )

    messages = render_chat_completions_messages(envelope)

    assert messages == [
        {"role": ChatCompletionRole.SYSTEM.value, "content": "Base policy"},
        {
            "role": ChatCompletionRole.USER.value,
            "content": "<context type='session_summary'>Earlier summary</context>",
        },
        {
            "role": ChatCompletionRole.USER.value,
            "content": "<context type='file_attachment'>file uuid=file-1</context>",
        },
        {"role": ChatCompletionRole.USER.value, "content": "Old question"},
        {"role": ChatCompletionRole.ASSISTANT.value, "content": "Old answer"},
        {"role": ChatCompletionRole.USER.value, "content": "Current question"},
    ]
    assert all(message["content"] != "Base policy" for message in messages[1:])


def test_prompt_envelope_renders_tools_as_top_level_schema() -> None:
    """Tool specs should render as Chat Completions tools, not prompt text."""
    envelope = PromptEnvelope(
        base_instructions="Base policy",
        context_items=[],
        history_items=[],
        current_user_item=UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="Current question"),
        ]),
        tools=[
            ToolDefinition(
                name="number_comparator",
                label="Number comparator",
                description="Compare numbers.",
                parameters={
                    "type": "object",
                    "properties": {"left": {"type": "number"}},
                },
                execute=_execute_tool,
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


def test_prompt_envelope_escapes_context_wrapper_content() -> None:
    """Context wrapper should not be breakable by context kind or content text."""
    envelope = PromptEnvelope(
        base_instructions="Base policy",
        context_items=[
            ContextItem(
                kind="runtime<context>",
                content="A < B & \"quoted\"",
            ),
        ],
        current_user_item=UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="Current question"),
        ]),
    )

    assert render_chat_completions_messages(envelope)[1] == {
        "role": ChatCompletionRole.USER.value,
        "content": (
            "<context type='runtime&lt;context&gt;'>"
            "A &lt; B &amp; &quot;quoted&quot;</context>"
        ),
    }
