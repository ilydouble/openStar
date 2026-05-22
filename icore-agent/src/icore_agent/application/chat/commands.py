"""Application commands for chat turn workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChatTurnCommand:
    """Command object for one authenticated chat turn."""

    message: str
    session_id: str
    stream: bool
    tenant_code: str
    agent_hint: str
    file_uuids: tuple[str, ...]
    user: dict[str, Any]

    @property
    def user_id(self) -> str:
        """Return the authenticated public user id."""
        return str(self.user["id"])
