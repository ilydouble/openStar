"""Agent chat schemas."""

import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32_000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream: bool = True
    tenant_code: str = ""
    agent_hint: str = ""
    file_uuids: list[str] = Field(default_factory=list)
    display_caption: str | None = Field(default=None, max_length=32_000)
    agent_message: str | None = Field(default=None, max_length=32_000)
    template_id: str | None = Field(default=None, max_length=64)
    incognito: bool = False
    # Pi mode: id of a previously-uploaded project workspace (PiWorkspace) the
    # user wants Pi to analyze. Backend resolves ownership, extracts it into a
    # sandbox, and binds the Pi agent's tools to that directory only.
    pi_workspace_id: str | None = Field(default=None, max_length=64)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
