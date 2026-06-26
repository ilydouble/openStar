"""Reasoning summary timeline item."""

from __future__ import annotations

from typing import Literal

from .base_item import SessionItemBase


class ReasoningItem(SessionItemBase):
    """A model reasoning summary item."""

    type: Literal["reasoning"] = "reasoning"
    text: str = ""
