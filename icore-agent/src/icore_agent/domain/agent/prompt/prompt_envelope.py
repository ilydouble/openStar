"""Provider-neutral prompt envelope for one agent model request."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    ToolCallItem,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition

PromptHistoryItem = UserMessageItem | AgentMessageItem
PromptTurnItem = AgentMessageItem | ToolCallItem


class PromptEnvelope(BaseModel):
    """Complete provider-neutral model request for one agent turn."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    base_instructions: str
    context_items: list[ContextItem] = Field(default_factory=list)
    history_items: list[PromptHistoryItem] = Field(default_factory=list)
    current_user_item: UserMessageItem
    turn_items: list[PromptTurnItem] = Field(default_factory=list)
    tools: list[ToolDefinition] = Field(default_factory=list)
    tool_choice: ToolChoice = ToolChoice.AUTO

    def usage_text(self) -> str:
        """Return a rough text representation for fallback usage estimation."""
        parts = [self.base_instructions]
        parts.extend(item.content for item in self.context_items)
        parts.extend(_history_item_text(item) for item in self.history_items)
        parts.append(self.current_user_item.to_text())
        parts.extend(_turn_item_text(item) for item in self.turn_items)
        return "\n\n".join(part for part in parts if part)


def _history_item_text(item: PromptHistoryItem) -> str:
    """Return model-visible text from a prior user or assistant item."""
    if isinstance(item, UserMessageItem):
        return item.to_text()
    return item.text


def _turn_item_text(item: PromptTurnItem) -> str:
    """Return model-visible text from a current-turn assistant or tool item."""
    if isinstance(item, AgentMessageItem):
        return item.text
    if item.result and item.result.content:
        return item.result.content
    if item.error:
        return item.error.message
    return item.function.arguments_text
