"""Agent session state schemas."""

from typing import Any

from pydantic import BaseModel, Field


class SessionTimelineItem(BaseModel):
    item_id: str
    type: str
    status: str
    payload: dict[str, Any]


class SessionTurnItem(BaseModel):
    turn_id: str
    status: str
    model: str | None = None
    provider: str | None = None
    usage: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    items: list[SessionTimelineItem]


class SessionAttachmentItem(BaseModel):
    file_uuid: str
    original_filename: str
    filename: str
    content_type: str
    mode: str
    download_url: str | None = None


class SessionStateResponse(BaseModel):
    session_id: str
    summary: str | None = None
    turns: list[SessionTurnItem]
    attachments: list[SessionAttachmentItem]


class SessionSummaryItem(BaseModel):
    title: str
    public_id: str
    created_at: int
    updated_at: int
    turn_count: int


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
