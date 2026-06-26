"""Strands Agent assembly for agent turns."""

from __future__ import annotations

from html import escape
from typing import Any

from strands import Agent
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager,
)
from strands.tools.executors import SequentialToolExecutor

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.prompt import (
    BuildSystemPromptOptions,
    PromptEnvelope,
    PromptHistoryItem,
    build_system_prompt,
    user_message_text,
)
from icore_agent.application.agent.tool import ToolDefinition
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.config import settings
from icore_agent.domain.agent.session import AgentMessageItem, ContextItem
from icore_agent.shared.logging.app_logger import get_logger

from .model_factory import create_litellm_model
from .tool_adapter import make_agent_tool

log = get_logger(__name__)


class StrandsPreparedAgentRunner:
    """Adapter that lets a Strands Agent consume a PromptEnvelope."""

    def __init__(self, agent: Agent) -> None:
        """Wrap one prepared Strands agent."""
        self._agent = agent

    @property
    def callback_handler(self) -> Any:
        """Return the underlying Strands callback handler."""
        return getattr(self._agent, "callback_handler", None)

    @callback_handler.setter
    def callback_handler(self, value: Any) -> None:
        """Patch the underlying Strands callback handler."""
        setattr(self._agent, "callback_handler", value)

    def __call__(self, prompt_envelope: PromptEnvelope) -> Any:
        """Render envelope history into Strands state and run current input."""
        self._agent.messages = _strands_messages(prompt_envelope)
        return self._agent(user_message_text(prompt_envelope.current_user_item))


def create_strands_orchestrator(
    callback_handler=None,
    summary: str | None = None,
    session_id: str = "",
    hooks: list[Any] | None = None,
    user_id: str = "",
    user_memory_prompt: str | None = None,
    file_service: Any | None = None,
    prompt_envelope: PromptEnvelope | None = None,
    tool_definitions: list[ToolDefinition] | None = None,
    **_: Any,
) -> StrandsPreparedAgentRunner:
    """Create a fresh Strands Agent via LiteLLM for one agent turn."""
    _ = summary, user_memory_prompt
    selected_model = settings.effective_model_id()
    model = create_litellm_model(
        model_id=selected_model,
        max_tokens=settings.agent_max_tokens,
        temperature=settings.agent_temperature,
        user_id=user_id,
        session_id=session_id,
    )

    conversation_manager = SlidingWindowConversationManager(window_size=40)
    definitions = list(
        tool_definitions
        or build_orchestrator_tool_definitions(
            session_id=session_id,
            user_id=user_id,
            file_service=file_service,
        )
    )
    system_prompt = (
        prompt_envelope.base_instructions
        if prompt_envelope is not None
        else str(build_system_prompt(BuildSystemPromptOptions()))
    )
    tools = [make_agent_tool(definition) for definition in definitions]

    orchestrator = Agent(
        model=model,
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=conversation_manager,
        tools=tools,
        hooks=hooks or [],
        # Execute tools serially to avoid provider RPM spikes when a single
        # response emits multiple tool calls.
        tool_executor=SequentialToolExecutor(),
    )

    log.info(
        "orchestrator_created",
        model=selected_model,
        n_tools=len(tools),
    )
    return StrandsPreparedAgentRunner(orchestrator)


def _strands_messages(prompt_envelope: PromptEnvelope) -> list[dict[str, Any]]:
    """Render context and prior history into Strands message state."""
    messages: list[dict[str, Any]] = []
    messages.extend(
        _text_message(ChatCompletionRole.USER.value, _context_block(item))
        for item in prompt_envelope.context_items
        if item.content
    )
    messages.extend(
        _history_message(item)
        for item in prompt_envelope.history_items
        if _history_item_text(item)
    )
    return messages


def _context_block(item: ContextItem) -> str:
    """Render one runtime context item in the shared model-visible wrapper."""
    return (
        f"<context type='{escape(item.kind, quote=True)}'>"
        f"{escape(item.content, quote=True)}</context>"
    )


def _history_message(item: PromptHistoryItem) -> dict[str, Any]:
    """Render one prior user or assistant item in the Strands message shape."""
    if isinstance(item, AgentMessageItem):
        return _text_message(ChatCompletionRole.ASSISTANT.value, item.text)
    return _text_message(ChatCompletionRole.USER.value, user_message_text(item))


def _history_item_text(item: PromptHistoryItem) -> str:
    """Return text used to decide whether a history item is model-visible."""
    if isinstance(item, AgentMessageItem):
        return item.text
    return user_message_text(item)


def _text_message(role: str, content: str) -> dict[str, Any]:
    """Render one text message in the Strands conversation shape."""
    return {
        "role": role,
        "content": [{"type": "text", "text": content}],
    }
