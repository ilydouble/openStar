"""Health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from ...config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    """Liveness probe — returns 200 when the service is up."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        service=settings.app_name,
    )


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def ready() -> HealthResponse:
    """Readiness probe — can add Redis/Bedrock connectivity checks here."""
    return HealthResponse(
        status="ready",
        version=settings.app_version,
        service=settings.app_name,
    )
