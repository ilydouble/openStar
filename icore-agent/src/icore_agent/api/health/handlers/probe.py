"""Health probe handlers."""

from ....config import settings
from ..schemas import HealthResponse


async def health() -> HealthResponse:
    """Liveness probe: returns 200 when the service is up."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        service=settings.app_name,
    )


async def ready() -> HealthResponse:
    """Readiness probe: can add Redis/Bedrock connectivity checks here."""
    return HealthResponse(
        status="ready",
        version=settings.app_version,
        service=settings.app_name,
    )
