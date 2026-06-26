"""Assistant message timeline item."""

from __future__ import annotations

from typing import Literal

from .base_item import SessionItemBase
from .session_item_type import SessionItemType


class AgentMessageItem(SessionItemBase):
    """An assistant response item, optionally built by streaming deltas."""

    type: Literal[SessionItemType.AGENT_MESSAGE] = SessionItemType.AGENT_MESSAGE
    text: str = ""
