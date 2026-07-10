"""Prompt builder for agent turn sampling steps."""

from __future__ import annotations

from typing import Any

from icore_agent.contexts.agent.application.prompt import build_agent_prompt_envelope
from icore_agent.contexts.agent.domain.context import TurnPromptSources
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ReasoningItem,
    SessionItem,
    ToolCallItem,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.tool import ToolDefinition
from icore_agent.contexts.agent.domain.turn import Turn


class AgentTurnPromptBuilder:
    """Build PromptEnvelope values from loaded sources and current turn state."""

    def __init__(self, *, command: Any, sources: TurnPromptSources) -> None:
        """Create a prompt builder for one user-triggered turn."""
        self._command = command
        self._sources = sources

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
            sources=self._sources,
            tool_definitions=tools,
        )
        return envelope.model_copy(update={
            "turn_items": _model_visible_turn_items(session_items),
        })


def _model_visible_turn_items(
    session_items: list[SessionItem],
) -> list[AgentMessageItem | ReasoningItem | ToolCallItem | UserMessageItem]:
    """Return current-turn items visible to the next model sample."""
    return [
        item
        for item in session_items
        if isinstance(item, (AgentMessageItem, ReasoningItem, ToolCallItem))
        or (
            isinstance(item, UserMessageItem)
            and item.metadata.get("runtime_input") == "steering"
        )
    ]
