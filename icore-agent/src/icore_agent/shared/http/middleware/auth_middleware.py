"""Auth middleware — validates Bearer tokens via iCore ft-base service.

Set AUTH_ENABLED=true in .env to activate.
The middleware calls ft-base's /user/tokenInfo endpoint and rejects
requests with invalid or expired tokens (401).

When AUTH_ENABLED=false (default for dev), all requests pass through.
"""

from __future__ import annotations

from typing import Any

import httpx
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from icore_agent.shared.logging.app_logger import get_logger

from ....config import settings
from ....infrastructure.control_plane.json_store import control_plane_store
from ....infrastructure.persistence.users.postgres_repositories import PostgresIdentityRepository
from ...auth.jwt import JWTValidationError, verify_access_token

log = get_logger(__name__)
account_repository = PostgresIdentityRepository(control_plane_store)

# Paths that skip auth entirely
_PUBLIC_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}
_PUBLIC_PREFIXES = (
    "/api/v1/account/register-trial",
    "/api/v1/account/login",
    "/api/v1/account/send-verification-code",
    "/api/v1/account/leads",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate bearer tokens before protected request handlers run."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Skip public paths and attach validated user info to request state."""
        # Skip public paths
        if request.url.path in _PUBLIC_PATHS or any(
            request.url.path.startswith(prefix) for prefix in _PUBLIC_PREFIXES
        ):
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            return JSONResponse({"code": 401, "message": "Missing Bearer token"}, status_code=401)

        local_user = self._validate_local_token(token)
        if local_user is not None:
            request.state.user = local_user
            return await call_next(request)

        user_info = await self._validate_token(token)
        if user_info is None:
            return JSONResponse({"code": 401, "message": "Invalid or expired token"}, status_code=401)

        # Attach user info to request state for downstream use
        request.state.user = user_info
        return await call_next(request)

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        """Extract a bearer token from the Authorization header."""
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return None

    @staticmethod
    async def _validate_token(token: str) -> dict[str, Any] | None:
        """Call ft-base token validation endpoint."""
        if not settings.icore_base_url:
            log.warning("auth_no_base_url_configured")
            return None
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{settings.icore_base_url}/user/tokenInfo",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Service-Secret": settings.icore_secret,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 200:
                        return data.get("data")
        except Exception as exc:
            log.error("auth_validation_error", error=str(exc))
        return None

    @staticmethod
    def _validate_local_token(token: str) -> dict[str, Any] | None:
        """Validate a local JWT or legacy opaque token and load the user profile."""
        try:
            claims = verify_access_token(
                token,
                secret=settings.jwt_secret,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
            )
        except JWTValidationError:
            return account_repository.get_user_by_token(token)

        return account_repository.get_user_by_id(claims["sub"])
