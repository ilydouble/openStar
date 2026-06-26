"""User message timeline item."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

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


class UserMessageItem(SessionItemBase):
    """A user message submitted at the start of a turn."""

    type: Literal[SessionItemType.USER_MESSAGE] = SessionItemType.USER_MESSAGE
    status: SessionItemStatus = SessionItemStatus.COMPLETED
    content: list[UserInput]

    def to_text(self) -> str:
        """Return model-visible text blocks from this user message."""
        return "\n".join(
            block.text or ""
            for block in self.content
            if block.text
        )
