"""Provider-neutral prompt envelope for one agent model request."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolChoice(StrEnum):
    """Provider-neutral tool selection modes."""

    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"


class BaseInstructions(BaseModel):
    """Stable instructions that should be rendered as the first system message."""

    model_config = ConfigDict(extra="forbid")

    text: str


class ContextItem(BaseModel):
    """Model-visible context material that is not conversation history."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    content: str
    role: Literal["user"] = "user"


class ModelVisibleItem(BaseModel):
    """One completed prior-turn item visible to the next model request."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str


class UserPromptItem(BaseModel):
    """Current-turn user prompt sent after context and prior history."""

    model_config = ConfigDict(extra="forbid")

    content: str


class ToolSpec(BaseModel):
    """Provider-neutral tool schema exposed to the model."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class PromptEnvelope(BaseModel):
    """Complete provider-neutral model request for one agent turn."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    base_instructions: BaseInstructions
    context_items: list[ContextItem] = Field(default_factory=list)
    history_items: list[ModelVisibleItem] = Field(default_factory=list)
    current_user_item: UserPromptItem
    tools: list[ToolSpec] = Field(default_factory=list)
    tool_choice: ToolChoice = ToolChoice.AUTO

    def usage_text(self) -> str:
        """Return a rough text representation for fallback usage estimation."""
        parts = [self.base_instructions.text]
        parts.extend(item.content for item in self.context_items)
        parts.extend(item.content for item in self.history_items)
        parts.append(self.current_user_item.content)
        return "\n\n".join(part for part in parts if part)
