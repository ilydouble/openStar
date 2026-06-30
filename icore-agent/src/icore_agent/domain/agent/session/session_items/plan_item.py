"""Agent plan timeline item."""

from __future__ import annotations

from typing import Literal

from .base_item import SessionItemBase
from .session_item_type import SessionItemType


class PlanItem(SessionItemBase):
    """An agent plan item shown in the turn timeline."""

    type: Literal[SessionItemType.PLAN] = SessionItemType.PLAN
    text: str = ""
