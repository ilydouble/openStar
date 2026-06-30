"""FastAPI application entry point."""

# ruff: noqa: E402,I001
# autopep8: off

# Split dotenv files must be loaded before LiteLLM import time.
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
from .interfaces.http.v1.envelope import install_api_envelope
from .interfaces.http.v1.router import include_api_routers
from .shared.http.middleware import (
    AuthMiddleware,
    BackendRequestLoggingMiddleware,
    RequestIdMiddleware,
)
from .shared.logging.app_logger import get_logger
from .application.usage.recording import (
    buffer_litellm_usage_event,
    build_litellm_usage_event,
    resolve_litellm_user_id,
)


log = get_logger(__name__)


# ── LiteLLM token usage logging ───────────────────────────────────────────────
# Fires after every LLM call in the process: agent turns, rolling-summary
# compression, memory extraction, and other model-backed work are counted.

def _log_token_usage(kwargs, completion_response, start_time, end_time) -> None:
    event = build_litellm_usage_event(kwargs, completion_response)
    if event is None:
        log.warning(
            "llm_token_usage_missing",
            model=kwargs.get("model", "unknown"),
        )
        return
    elapsed = (end_time - start_time).total_seconds()
    buffered = buffer_litellm_usage_event(event)
    log.info(
        "llm_token_usage",
        model=event["model"],
        prompt_tokens=event["prompt_tokens"],
        completion_tokens=event["completion_tokens"],
        total_tokens=event["total_tokens"],
        elapsed_s=round(elapsed, 2),
        buffered=buffered,
    )
    if buffered:
        return
    user_id = resolve_litellm_user_id(kwargs)
    if not user_id:
        log.warning(
            "llm_token_usage_skipped",
            reason="missing_user_id",
            model=event["model"],
        )
        return
    usage_service.record_llm_usage(
        user_id=user_id,
        session_id=str(event.get("session_id") or ""),
        model=event["model"],
        prompt_tokens=int(event["prompt_tokens"]),
        completion_tokens=int(event["completion_tokens"]),
        total_tokens=int(event["total_tokens"]),
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
        description="iCore Agent Platform — self-built agent runtime.",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    install_api_envelope(app)

    # ── CORS ──────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
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
