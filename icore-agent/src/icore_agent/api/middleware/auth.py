"""Auth middleware — validates Bearer tokens via iCore ft-base service.

Set AUTH_ENABLED=true in .env to activate.
The middleware calls ft-base's /user/tokenInfo endpoint and rejects
requests with invalid or expired tokens (401).

When AUTH_ENABLED=false (default for dev), all requests pass through.
"""

from __future__ import annotations

import httpx
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ...config import settings

log = structlog.get_logger()

# Paths that skip auth entirely
_PUBLIC_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip public paths
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            return JSONResponse({"code": 401, "message": "Missing Bearer token"}, status_code=401)

        user_info = await self._validate_token(token)
        if user_info is None:
            return JSONResponse({"code": 401, "message": "Invalid or expired token"}, status_code=401)

        # Attach user info to request state for downstream use
        request.state.user = user_info
        return await call_next(request)

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return None

    @staticmethod
    async def _validate_token(token: str) -> dict | None:
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
