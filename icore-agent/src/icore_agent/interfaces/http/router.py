"""Top-level FastAPI router composition."""

from fastapi import FastAPI

from .account import router as account_router
from .agent import router as agent_router
from .health import router as health_router
from .knowledge import router as knowledge_router
from .payment import router as payment_router


def include_api_routers(app: FastAPI) -> None:
    """Register all business-domain routers on the FastAPI app."""
    app.include_router(health_router)
    app.include_router(account_router)
    app.include_router(agent_router)
    app.include_router(knowledge_router)
    app.include_router(payment_router)
