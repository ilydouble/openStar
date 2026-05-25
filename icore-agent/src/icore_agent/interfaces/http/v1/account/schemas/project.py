"""Project synchronization schemas."""

from pydantic import BaseModel, Field


class ProjectSyncRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=120)
    project_title: str = Field(..., min_length=1, max_length=200)
    scenario_id: str = Field(default="", max_length=80)
    session_id: str = Field(..., min_length=1, max_length=120)
    session_title: str = Field(..., min_length=1, max_length=200)
    session_subtitle: str = Field(default="", max_length=500)
    attachment_count: int = Field(default=0, ge=0, le=500)
