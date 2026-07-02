"""Assemble provider-neutral prompt envelopes for agent turns."""

from __future__ import annotations

from typing import Any

from icore_agent.config import settings
from icore_agent.domain.agent.context import TurnPromptSources
from icore_agent.domain.agent.prompt import (
    PromptEnvelope,
    assemble_prompt_envelope,
    build_base_instructions,
)
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition


def build_agent_prompt_envelope(
    *,
    command: Any,
    sources: TurnPromptSources,
    tool_definitions: list[ToolDefinition],
) -> PromptEnvelope:
    """Build the model-visible prompt envelope for one agent turn."""
    return assemble_prompt_envelope(
        base_instructions=build_base_instructions(),
        sources=sources,
        user_text=command.agent_message or command.message,
        tools=tool_definitions,
        tool_choice=ToolChoice.AUTO,
        include_image_inputs=settings.agent_model_supports_vision,
    )
