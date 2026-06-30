"""Base value objects shared by session timeline items."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from icore_agent.domain.identifiers import uuid7
from icore_agent.shared.time.utils import utc_now


def _new_id() -> str:
    """Return a stable public domain id."""
    return str(uuid7())


class SessionItemStatus(StrEnum):
    """Lifecycle status shared by user-visible session items."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionItemBase(BaseModel):
    """Base model for one item in a chat turn timeline."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(default_factory=_new_id)
    status: SessionItemStatus = SessionItemStatus.IN_PROGRESS
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
