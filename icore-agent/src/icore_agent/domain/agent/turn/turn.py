"""Domain model for one user-intent execution turn."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from domain.agent.session import (
    AgentMessageItem,
    SessionItem,
)
from icore_agent.domain.identifiers import uuid7

from .turn_error import TurnError


def _new_id() -> str:
    """Return a stable public domain id."""
    return str(uuid7())


class TurnStatus(StrEnum):
    """Lifecycle status for one agent turn."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class Turn(BaseModel):
    """A user-intent execution transaction containing ordered timeline items."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(default_factory=_new_id)
    session_id: str
    items: list[SessionItem] = Field(default_factory=list)
    status: TurnStatus = TurnStatus.IN_PROGRESS
    error: TurnError | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None

    def upsert_item(self, session_item: SessionItem) -> None:
        """Insert or replace an item with the same id."""
        for index, existing in enumerate(self.items):
            if existing.id == session_item.id:
                self.items[index] = session_item
                return
        self.items.append(session_item)

    def reply_text(self) -> str:
        """Return the last assistant message text produced in this turn."""
        for item in reversed(self.items):
            if isinstance(item, AgentMessageItem):
                return item.text
        return ""
