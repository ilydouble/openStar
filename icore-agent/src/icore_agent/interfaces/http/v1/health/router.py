"""Health API router."""

from fastapi import APIRouter

from .handlers import health, ready
from .schemas import HealthResponse

router = APIRouter(tags=["health"])

router.get("/health", response_model=HealthResponse, summary="Health check")(health)
router.get("/ready", response_model=HealthResponse, summary="Readiness probe")(ready)
