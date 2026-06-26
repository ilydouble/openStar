"""Assistant message timeline item."""

from __future__ import annotations

from typing import Literal

from .base_item import SessionItemBase


class AgentMessageItem(SessionItemBase):
    """An assistant response item, optionally built by streaming deltas."""

    type: Literal["agent_message"] = "agent_message"
    text: str = ""
