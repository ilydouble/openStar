"""Pure prompt envelope assembly rules for agent turns."""

from __future__ import annotations

from icore_agent.contexts.agent.domain.context import TurnPromptSources
from icore_agent.contexts.agent.domain.session import (
    ContextItem,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.tool import ToolChoice, ToolDefinition

from .prompt_envelope import PromptEnvelope


def build_context_items(
    sources: TurnPromptSources,
    *,
    include_image_refs: bool = True,
) -> list[ContextItem]:
    """Build model-visible context items from loaded prompt sources."""
    items: list[ContextItem] = []
    if sources.summary:
        items.append(ContextItem(
            kind="session_summary",
            content=f"Earlier conversation summary:\n{sources.summary}",
        ))
    if sources.user_memory_prompt:
        items.append(ContextItem(
            kind="user_memory",
            content=sources.user_memory_prompt,
        ))
    items.extend(sources.rag_context_items)
    if include_image_refs:
        items.extend(
            attachment.to_context_item()
            for attachment in sources.image_attachments
        )
    items.extend(
        attachment.to_context_item()
        for attachment in sources.file_attachments
    )
    return items


def build_current_user_item(
    sources: TurnPromptSources,
    user_text: str,
    *,
    include_image_inputs: bool = False,
) -> UserMessageItem:
    """Build the current user prompt item from text and image sources."""
    inputs = [
        UserInput(
            type=UserInputType.TEXT,
            text=user_text,
        )
    ]
    if include_image_inputs:
        for attachment in sources.image_attachments:
            inputs.extend(attachment.to_user_inputs())
    return UserMessageItem(content=inputs)


def assemble_prompt_envelope(
    *,
    base_instructions: str,
    sources: TurnPromptSources,
    user_text: str,
    tools: list[ToolDefinition],
    tool_choice: ToolChoice = ToolChoice.AUTO,
    include_image_inputs: bool = False,
) -> PromptEnvelope:
    """Build a provider-neutral prompt envelope from loaded prompt sources."""
    return PromptEnvelope(
        base_instructions=base_instructions,
        context_items=build_context_items(
            sources,
            include_image_refs=not include_image_inputs,
        ),
        history_items=sources.history_items,
        current_user_item=build_current_user_item(
            sources,
            user_text,
            include_image_inputs=include_image_inputs,
        ),
        tools=tools,
        tool_choice=tool_choice,
    )
