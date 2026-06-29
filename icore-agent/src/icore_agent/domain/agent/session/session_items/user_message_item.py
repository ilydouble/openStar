"""User message timeline item."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .base_item import SessionItemBase, SessionItemStatus
from .session_item_type import SessionItemType


class UserInputType(StrEnum):
    """Supported user input blocks."""

    TEXT = "text"
    IMAGE = "image"


class UserInput(BaseModel):
    """One typed block in a user message item."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    type: UserInputType
    text: str | None = None
    image_file_uuid: str | None = None
    image_url: str | None = None


class UserMessageItem(SessionItemBase):
    """A user message submitted at the start of a turn."""

    type: Literal[SessionItemType.USER_MESSAGE] = SessionItemType.USER_MESSAGE
    status: SessionItemStatus = SessionItemStatus.COMPLETED
    content: list[UserInput]
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Runtime metadata for application-owned references such as "
            "attachment UUIDs, display captions, and template identifiers. "
            "This metadata is persisted for UI/session hydration but is not "
            "rendered as message text by prompt adapters."
        ),
    )

    def to_text(self) -> str:
        """Return model-visible text blocks from this user message."""
        return "\n".join(
            block.text or ""
            for block in self.content
            if block.text
        )
