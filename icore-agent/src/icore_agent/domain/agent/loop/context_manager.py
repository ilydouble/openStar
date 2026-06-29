"""Prompt context manager protocol for agent loop execution."""

from __future__ import annotations

from typing import Protocol

from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import SessionItem
from icore_agent.domain.agent.tool import ToolDefinition
from icore_agent.domain.agent.turn import Turn


class PromptContextManager(Protocol):
    """Build model-visible prompts from loaded context and current turn state."""

    def build_prompt(
        self,
        *,
        turn: Turn,
        session_items: list[SessionItem],
        tools: list[ToolDefinition],
    ) -> PromptEnvelope:
        """Build the provider-neutral prompt envelope for one sampling step."""
        ...
