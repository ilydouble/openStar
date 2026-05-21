"""FastAPI application entry point."""

# ruff: noqa: E402,I001
# autopep8: off

# Split dotenv files must be loaded before LiteLLM/Strands import time.
from .config.dotenv import load_domain_dotenvs

load_domain_dotenvs()

from contextlib import asynccontextmanager

import litellm
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .infrastructure.control_plane.json_store import control_plane_store
from .interfaces.http.v1.dependencies import usage_service
from .interfaces.http.v1.router import include_api_routers
from .shared.http.middleware import (
    AuthMiddleware,
    BackendRequestLoggingMiddleware,
    RequestIdMiddleware,
)
from .shared.logging.app_logger import get_logger
from .shared.runtime.user_context import current_runtime_user


log = get_logger(__name__)


# ── LiteLLM token usage logging ───────────────────────────────────────────────
# Fires after EVERY LLM call in the process: orchestrator turns, sub-agent turns,
# rolling-summary compression, memU extraction — all are counted.

def _log_token_usage(kwargs, completion_response, start_time, end_time) -> None:
    usage = getattr(completion_response, "usage", None)
    if usage is None:
        return
    elapsed = (end_time - start_time).total_seconds()
    log.info(
        "llm_token_usage",
        model=kwargs.get("model", "unknown"),
        prompt_tokens=getattr(usage, "prompt_tokens", 0),
        completion_tokens=getattr(usage, "completion_tokens", 0),
        total_tokens=getattr(usage, "total_tokens", 0),
        elapsed_s=round(elapsed, 2),
    )
    user = current_runtime_user()
    if user:
        usage_service.record_llm_usage(
            user_id=user["id"],
            session_id=str(kwargs.get("metadata", {}).get("session_id", "")),
            model=kwargs.get("model", "unknown"),
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        )


litellm.success_callback = [_log_token_usage]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Log startup and shutdown without relying on deprecated FastAPI events."""
    log.info(
        "icore_agent_started",
        version=settings.app_version,
        debug=settings.debug,
        model=settings.model_id,
    )
    if settings.import_json_users_on_startup:
        from .infrastructure.persistence.users.json_import import import_legacy_users_from_store

        imported = import_legacy_users_from_store(control_plane_store)
        if imported:
            log.info("json_users_imported", count=imported)
    try:
        yield
    finally:
        log.info("icore_agent_stopped")


def create_app() -> FastAPI:
    """Build the FastAPI application with all middleware and routers attached."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "iCore Agent Platform — multi-agent orchestration powered by "
            "AWS Strands Agents SDK and mini-SWE-agent sequential executor."
        ),
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
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

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(BackendRequestLoggingMiddleware)

    # ── Routers ───────────────────────────────────────────
    include_api_routers(app)

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
