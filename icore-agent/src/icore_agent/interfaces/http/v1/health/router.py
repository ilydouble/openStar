"""Health API router."""

from fastapi import APIRouter

from ..envelope import ApiEnvelopeRoute
from .handlers import health, ready
from .schemas import HealthResponse

router = APIRouter(tags=["health"], route_class=ApiEnvelopeRoute)

router.get("/health", response_model=HealthResponse,
           summary="Health check")(health)
router.get("/ready", response_model=HealthResponse,
           summary="Readiness probe")(ready)
