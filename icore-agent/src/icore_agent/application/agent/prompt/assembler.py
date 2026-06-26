"""Assemble provider-neutral prompt envelopes for agent turns."""

from __future__ import annotations

from typing import Any

from icore_agent.domain.agent.prompt import (
    PromptEnvelope,
    build_base_instructions,
)
from icore_agent.application.agent.context.agent_context import AgentContext
from icore_agent.domain.agent.session import (
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
        context_items=context.to_context_items(),
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
