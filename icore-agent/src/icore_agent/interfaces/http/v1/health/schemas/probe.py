"""Health probe schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str
