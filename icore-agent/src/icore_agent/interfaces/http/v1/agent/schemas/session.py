"""Agent session state schemas."""

from pydantic import BaseModel


class SessionStateResponse(BaseModel):
    session_id: str
    summary: str | None = None
    messages: list[dict]
    attachments: list[dict]
