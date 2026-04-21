"""FastAPI application entry point."""

# load_dotenv 必须在所有其他 import 之前执行
# 这样 LiteLLM、strands 等库初始化时就能从 os.environ 读到 API Key
from dotenv import load_dotenv
load_dotenv()

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.routers import agent as agent_router
from .api.routers import health as health_router
from .api.middleware.auth import AuthMiddleware

log = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "iCore Agent Platform — multi-agent orchestration powered by "
            "AWS Strands Agents SDK and mini-SWE-agent sequential executor."
        ),
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # ── CORS ──────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Auth middleware (optional, delegates to ft-base) ──
    if settings.auth_enabled:
        app.add_middleware(AuthMiddleware)

    # ── Routers ───────────────────────────────────────────
    app.include_router(health_router.router, tags=["health"])
    app.include_router(agent_router.router, prefix="/api/v1/agent", tags=["agent"])

    # ── Lifecycle ─────────────────────────────────────────
    @app.on_event("startup")
    async def _startup() -> None:
        log.info(
            "icore_agent_started",
            version=settings.app_version,
            debug=settings.debug,
            model=settings.model_id,
        )

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        log.info("icore_agent_stopped")

    return app


app = create_app()


def start() -> None:
    """CLI entry-point (see pyproject.toml [project.scripts])."""
    uvicorn.run(
        "icore_agent.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    start()
