"""Model reasoning timeline item."""

from __future__ import annotations

from typing import Literal

from .base_item import SessionItemBase
from .session_item_type import SessionItemType


class ReasoningItem(SessionItemBase):
    """Model reasoning content captured for one sampling step."""

    type: Literal[SessionItemType.REASONING] = SessionItemType.REASONING
    text: str = ""
