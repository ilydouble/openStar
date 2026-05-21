"""Agent session state schemas."""

from pydantic import BaseModel, Field


class SessionStateResponse(BaseModel):
    session_id: str
    summary: str | None = None
    messages: list[dict]
    attachments: list[dict]


class SessionSummaryItem(BaseModel):
    title: str
    public_id: str
    created_at: int
    updated_at: int
    message_count: int


class SessionListResponse(BaseModel):
    sessions: list[SessionSummaryItem]
    total: int
    limit: int
    offset: int = Field(default=0, ge=0)


class SessionSearchResultItem(BaseModel):
    title: str
    public_id: str
    updated_at: int
    rank: float
    snippet: str


class SessionSearchResponse(BaseModel):
    query: str
    sessions: list[SessionSearchResultItem]
    total: int
    limit: int
    offset: int = Field(default=0, ge=0)
