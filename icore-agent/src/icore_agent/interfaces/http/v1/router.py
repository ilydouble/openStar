"""Top-level FastAPI router composition."""

from fastapi import FastAPI

from icore_agent.contexts.agent.interfaces.http.v1.router import router as agent_router
from icore_agent.contexts.account.interfaces.http.v1.router import router as account_router
from icore_agent.contexts.files.interfaces.http.v1.router import router as files_router
from icore_agent.contexts.knowledge.interfaces.http.v1.router import router as knowledge_router
from icore_agent.contexts.payment.interfaces.http.v1.router import router as payment_router

from .envelope import install_api_envelope
from .health import router as health_router


def include_api_routers(app: FastAPI) -> None:
    """Register all business-domain routers on the FastAPI app."""
    install_api_envelope(app)
    app.include_router(health_router)
    app.include_router(account_router)
    app.include_router(agent_router)
    app.include_router(files_router)
    app.include_router(knowledge_router)
    app.include_router(payment_router)
