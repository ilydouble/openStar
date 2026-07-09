"""Per-step prompt envelope builder protocol for agent loop execution."""

from __future__ import annotations

from typing import Protocol

from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import SessionItem
from icore_agent.contexts.agent.domain.tool import ToolDefinition
from icore_agent.contexts.agent.domain.turn import Turn


class PromptContextManager(Protocol):
    """Build model-visible prompts from loaded sources and turn-local items."""

    def build_prompt(
        self,
        *,
        turn: Turn,
        session_items: list[SessionItem],
        tools: list[ToolDefinition],
    ) -> PromptEnvelope:
        """Build the provider-neutral prompt envelope for one sampling step."""
        ...
