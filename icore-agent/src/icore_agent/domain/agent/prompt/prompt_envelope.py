"""Provider-neutral prompt envelope for one agent model request."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from icore_agent.domain.agent.session import (
    AgentMessageItem,
    ContextItem,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition

PromptHistoryItem = UserMessageItem | AgentMessageItem


class PromptEnvelope(BaseModel):
    """Complete provider-neutral model request for one agent turn."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    base_instructions: str
    context_items: list[ContextItem] = Field(default_factory=list)
    history_items: list[PromptHistoryItem] = Field(default_factory=list)
    current_user_item: UserMessageItem
    tools: list[ToolDefinition] = Field(default_factory=list)
    tool_choice: ToolChoice = ToolChoice.AUTO

    def usage_text(self) -> str:
        """Return a rough text representation for fallback usage estimation."""
        parts = [self.base_instructions]
        parts.extend(item.content for item in self.context_items)
        parts.extend(_history_item_text(item) for item in self.history_items)
        parts.append(self.current_user_item.to_text())
        return "\n\n".join(part for part in parts if part)


def _history_item_text(item: PromptHistoryItem) -> str:
    """Return model-visible text from a prior user or assistant item."""
    if isinstance(item, UserMessageItem):
        return item.to_text()
    return item.text
