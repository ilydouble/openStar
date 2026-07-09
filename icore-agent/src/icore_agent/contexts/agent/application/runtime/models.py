"""Provider-neutral runtime state for active agent runs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentRunRecord(BaseModel):
    """Durable runtime metadata for one active agent run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    session_id: str
    user_id: str
    turn_id: str | None = None
    started_at: datetime
    abort_requested: bool = False


class QueuedAgentInput(BaseModel):
    """One user input queued through the runtime control surface."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1)
    session_id: str
    user_id: str
    created_at: datetime


class AgentRunControlResult(BaseModel):
    """Public result returned by runtime control methods."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    session_id: str
    run_id: str | None = None
