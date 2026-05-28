"""Account memory management schemas."""

from pydantic import BaseModel, Field


class UpdateMemoryFactRequest(BaseModel):
    """Request body for updating one memory fact value."""

    value: str = Field(min_length=1, max_length=200)
