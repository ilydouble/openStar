"""Sequential task schemas."""

from pydantic import BaseModel, Field


class SequentialRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=8_000)
    use_docker: bool = False


class SequentialResponse(BaseModel):
    status: str
    output: str
    steps: int
