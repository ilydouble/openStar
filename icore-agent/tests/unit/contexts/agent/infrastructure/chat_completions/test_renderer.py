"""Tests for provider-neutral agent prompt envelopes."""

from __future__ import annotations

from icore_agent.contexts.agent.domain import ChatCompletionRole
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ContextItem,
    ReasoningItem,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.tool import ToolChoice, ToolDefinition
from icore_agent.contexts.agent.infrastructure.chat_completions import (
    render_chat_completions_messages,
    render_chat_completions_tools,
)


def _execute_tool(*_: object) -> str:
    """Return a stable test result for ToolDefinition construction."""
    return "ok"


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


def test_prompt_envelope_renders_current_user_images_as_multimodal_content() -> None:
    """Current user image inputs should render as Chat Completions image content."""
    envelope = PromptEnvelope(
        base_instructions="Base policy",
        current_user_item=UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="Describe this chart"),
            UserInput(
                type=UserInputType.IMAGE,
                image_file_uuid="img-1",
                image_url="https://files.example/img-1",
            ),
        ]),
    )

    messages = render_chat_completions_messages(envelope)

    assert messages[-1] == {
        "role": ChatCompletionRole.USER.value,
        "content": [
            {"type": "text", "text": "Describe this chart"},
            {
                "type": "image_url",
                "image_url": {"url": "https://files.example/img-1"},
            },
        ],
    }


def test_renderer_projects_turn_tool_state_to_messages() -> None:
    """Renderer should convert current-turn tool state only at the provider boundary."""
    tool_call = ToolCallItem(
        provider_tool_call_id="tool-1",
        function=ToolFunction(
            name="number_comparator",
            arguments_text='{"left":2,"right":1}',
            arguments_json={"left": 2, "right": 1},
        ),
        status=ToolCallStatus.COMPLETED,
        result=ToolCallResult(content='{"comparison":"greater"}'),
    )
    envelope = _turn_envelope(
        turn_items=[
            ReasoningItem(text="I need the comparator tool."),
            tool_call,
        ],
    )

    messages = render_chat_completions_messages(envelope)

    assert messages[-2] == {
        "role": ChatCompletionRole.ASSISTANT.value,
        "content": None,
        "reasoning_content": "I need the comparator tool.",
        "tool_calls": [{
            "id": "tool-1",
            "type": "function",
            "function": {
                "name": "number_comparator",
                "arguments": '{"left":2,"right":1}',
            },
        }],
    }
    assert messages[-1] == {
        "role": ChatCompletionRole.TOOL.value,
        "tool_call_id": "tool-1",
        "name": "number_comparator",
        "content": '{"comparison":"greater"}',
    }


def test_renderer_reconstructs_tool_request_without_reasoning() -> None:
    """Renderer should precede standalone tool state with an assistant request."""
    tool_call = ToolCallItem(
        provider_tool_call_id="tool-1",
        function=ToolFunction(
            name="number_comparator",
            arguments_text='{"left":2,"right":1}',
        ),
        status=ToolCallStatus.COMPLETED,
        result=ToolCallResult(content='{"comparison":"greater"}'),
    )

    messages = render_chat_completions_messages(
        _turn_envelope(turn_items=[tool_call]),
    )

    assert messages[-2]["role"] == ChatCompletionRole.ASSISTANT.value
    assert messages[-2]["content"] is None
    assert messages[-2]["tool_calls"][0]["id"] == "tool-1"
    assert messages[-1]["role"] == ChatCompletionRole.TOOL.value


def test_renderer_pairs_reasoning_with_final_answer() -> None:
    """Renderer should preserve reasoning-before-answer sampling order."""
    envelope = _turn_envelope(turn_items=[
        ReasoningItem(text="Use the observed result."),
        AgentMessageItem(text="2 is greater than 1."),
    ])

    messages = render_chat_completions_messages(envelope)

    assert messages[-1] == {
        "role": ChatCompletionRole.ASSISTANT.value,
        "content": "2 is greater than 1.",
        "reasoning_content": "Use the observed result.",
    }


def test_renderer_projects_turn_user_items_to_messages() -> None:
    """Renderer should expose runtime steering as current-turn user messages."""
    envelope = _turn_envelope(turn_items=[
        AgentMessageItem(text="I will inspect that."),
        UserMessageItem(content=[
            UserInput(
                type=UserInputType.TEXT,
                text="Actually avoid network access.",
            ),
        ]),
    ])

    messages = render_chat_completions_messages(envelope)

    assert messages[-2] == {
        "role": ChatCompletionRole.ASSISTANT.value,
        "content": "I will inspect that.",
    }
    assert messages[-1] == {
        "role": ChatCompletionRole.USER.value,
        "content": "Actually avoid network access.",
    }


def _turn_envelope(
    *,
    turn_items: list[
        AgentMessageItem | ReasoningItem | ToolCallItem | UserMessageItem
    ],
) -> PromptEnvelope:
    """Build a prompt envelope containing current-turn timeline items."""
    return PromptEnvelope(
        base_instructions="Base policy",
        current_user_item=UserMessageItem(content=[
            UserInput(type=UserInputType.TEXT, text="Which is larger?"),
        ]),
        turn_items=turn_items,
        tools=[ToolDefinition(
            name="number_comparator",
            label="Number comparator",
            description="Compare numbers.",
            parameters={"type": "object"},
            execute=_execute_tool,
        )],
        tool_choice=ToolChoice.AUTO,
    )
