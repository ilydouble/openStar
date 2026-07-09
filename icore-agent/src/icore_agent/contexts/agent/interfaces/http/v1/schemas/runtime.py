"""HTTP schemas for agent runtime control APIs."""

from pydantic import BaseModel, Field


class AgentRuntimeInputRequest(BaseModel):
    """Request body for runtime steering and follow-up input."""

    message: str = Field(..., min_length=1, max_length=32_000)


class AgentRuntimeControlResponse(BaseModel):
    """Response body for accepted runtime control commands."""

    accepted: bool
    session_id: str
    run_id: str | None = None
