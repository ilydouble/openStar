"""Prompt context manager for agent turn sampling steps."""

from __future__ import annotations

from typing import Any

from icore_agent.application.agent.prompt import build_agent_prompt_envelope
from icore_agent.domain.agent.context import AgentContext
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    SessionItem,
    ToolCallItem,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolDefinition
from icore_agent.domain.agent.turn import Turn


class AgentPromptContextManager:
    """Build PromptEnvelope values from loaded context and current turn state."""

    def __init__(self, *, command: Any, context: AgentContext) -> None:
        """Create a manager for one user-triggered turn."""
        self._command = command
        self._context = context

    def build_prompt(
        self,
        *,
        turn: Turn,
        session_items: list[SessionItem],
        tools: list[ToolDefinition],
    ) -> PromptEnvelope:
        """Build the provider-neutral prompt for one model sampling step."""
        _ = turn
        envelope = build_agent_prompt_envelope(
            command=self._command,
            context=self._context,
            tool_definitions=tools,
        )
        return envelope.model_copy(update={
            "turn_items": _model_visible_turn_items(session_items),
        })


def _model_visible_turn_items(
    session_items: list[SessionItem],
) -> list[AgentMessageItem | ToolCallItem | UserMessageItem]:
    """Return current-turn assistant/tool items visible to the next sample."""
    return [
        item
        for item in session_items
        if isinstance(item, (AgentMessageItem, ToolCallItem))
        or (
            isinstance(item, UserMessageItem)
            and item.metadata.get("runtime_input") == "steering"
        )
    ]
