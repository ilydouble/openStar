"""Provider-neutral prompt envelope for one agent model request."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    UserMessageItem,
)

PromptHistoryItem = UserMessageItem | AgentMessageItem


class ToolChoice(StrEnum):
    """Provider-neutral tool selection modes."""

    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"


class ToolSpec(BaseModel):
    """Provider-neutral tool schema exposed to the model."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class PromptEnvelope(BaseModel):
    """Complete provider-neutral model request for one agent turn."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    base_instructions: str
    context_items: list[ContextItem] = Field(default_factory=list)
    history_items: list[PromptHistoryItem] = Field(default_factory=list)
    current_user_item: UserMessageItem
    tools: list[ToolSpec] = Field(default_factory=list)
    tool_choice: ToolChoice = ToolChoice.AUTO

    def usage_text(self) -> str:
        """Return a rough text representation for fallback usage estimation."""
        parts = [self.base_instructions]
        parts.extend(item.content for item in self.context_items)
        parts.extend(_history_item_text(item) for item in self.history_items)
        parts.append(user_message_text(self.current_user_item))
        return "\n\n".join(part for part in parts if part)


def user_message_text(item: UserMessageItem) -> str:
    """Return model-visible text blocks from one user message item."""
    return "\n".join(
        block.text or ""
        for block in item.content
        if block.text
    )


def _history_item_text(item: PromptHistoryItem) -> str:
    """Return model-visible text from a prior user or assistant item."""
    if isinstance(item, UserMessageItem):
        return user_message_text(item)
    return item.text
