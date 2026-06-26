"""Agent plan timeline item."""

from __future__ import annotations

from typing import Literal

from .base_item import SessionItemBase


class PlanItem(SessionItemBase):
    """An agent plan item shown in the turn timeline."""

    type: Literal["plan"] = "plan"
    text: str = ""
