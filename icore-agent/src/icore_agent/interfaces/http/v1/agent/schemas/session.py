"""Agent session state schemas."""

from typing import Any

from pydantic import BaseModel, Field


class SessionMessageItem(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] | None = None


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
    messages: list[SessionMessageItem]
    attachments: list[SessionAttachmentItem]


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
