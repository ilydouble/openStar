"""ASGI middleware that sends backend HTTP access logs to logging-service."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ...logging import LogLevel
from ...logging.logging_service_client import default_logging_client
from ..request.request_context import get_request_id
from ..request.request_id_management import REQUEST_ID_HEADER, request_id_from_headers

log = logging.getLogger(__name__)


class BackendRequestLoggingMiddleware:
    """Emit one icore-backend access log for each HTTP request lifecycle."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        client: Any | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Wrap an ASGI app with non-blocking logging-service access logs."""
        self.app = app
        self.client = client or default_logging_client
        self.now = now or (lambda: datetime.now(UTC))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Capture the response status and emit a backend request log."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_timestamp = self.now()
        start = time.perf_counter()
        status_code: int | None = None

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        except Exception as exc:
            self._emit_request_event(
                scope,
                headers,
                request_timestamp=request_timestamp,
                elapsed_ms=self._elapsed_ms(start),
                final_status_code=status_code or 500,
                error_type=type(exc).__name__,
            )
            raise

        self._emit_request_event(
            scope,
            headers,
            request_timestamp=request_timestamp,
            elapsed_ms=self._elapsed_ms(start),
            final_status_code=status_code or 500,
            error_type=None,
        )

    def _emit_request_event(
        self,
        scope: Scope,
        headers: Headers,
        *,
        request_timestamp: datetime,
        elapsed_ms: int,
        final_status_code: int,
        error_type: str | None,
    ) -> None:
        """Build and enqueue the logging-service backend access event."""
        request_id = self._request_id(scope, headers)
        metadata = {
            "request_timestamp": request_timestamp.isoformat(),
            "request_id": request_id,
            "method": scope.get("method", ""),
            "path": scope.get("path", ""),
            "query": self._query(scope),
            "client_ip": self._client_ip(scope, headers),
            "user_agent": headers.get("user-agent", ""),
            "user_id": self._user_id(scope),
            "roles": self._roles(scope),
            "final_status_code": final_status_code,
            "request_elapsed_time": elapsed_ms,
            "error_type": error_type,
        }

        try:
            self.client.emit_event(
                self._level(final_status_code),
                message="backend request",
                service="icore-backend",
                trace_id=request_id,
                metadata=metadata,
                timestamp=request_timestamp,
            )
        except Exception as exc:  # noqa: BLE001 - logging must not break requests.
            log.warning("backend_request_log_emit_failed: %s", exc)

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        """Return elapsed request time in whole milliseconds."""
        return max(0, int((time.perf_counter() - start) * 1000))

    @staticmethod
    def _request_id(scope: Scope, headers: Headers) -> str:
        """Resolve the canonical request id from scope state, context, or headers."""
        state = scope.get("state") or {}
        state_request_id = state.get(
            "request_id") if isinstance(state, dict) else None
        if state_request_id:
            return str(state_request_id)
        return get_request_id() or request_id_from_headers(headers) or headers.get(
            REQUEST_ID_HEADER, ""
        )

    @staticmethod
    def _query(scope: Scope) -> str:
        """Return the raw query string without a leading question mark."""
        raw = scope.get("query_string", b"")
        if isinstance(raw, bytes):
            return raw.decode("latin-1")
        return str(raw)

    @staticmethod
    def _client_ip(scope: Scope, headers: Headers) -> str:
        """Resolve the client IP as forwarded by the gateway when present."""
        forwarded_for = headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        real_ip = headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
        client = scope.get("client")
        if isinstance(client, tuple) and client:
            return str(client[0])
        return ""

    @staticmethod
    def _user(scope: Scope) -> Mapping[str, Any]:
        """Return the authenticated user object from request state when available."""
        state = scope.get("state") or {}
        if isinstance(state, dict) and isinstance(state.get("user"), Mapping):
            return state["user"]
        return {}

    @classmethod
    def _user_id(cls, scope: Scope) -> str:
        """Return a stable user id from the authenticated request state."""
        user = cls._user(scope)
        return str(user.get("id") or user.get("user_id") or user.get("sub") or "")

    @classmethod
    def _roles(cls, scope: Scope) -> list[str]:
        """Return normalized role names from the authenticated request state."""
        roles = cls._user(scope).get("roles") or []
        if isinstance(roles, str):
            return [roles]
        if isinstance(roles, list):
            return [str(role) for role in roles]
        return []

    @staticmethod
    def _level(status_code: int) -> LogLevel:
        """Map HTTP status codes to logging-service severities."""
        if status_code >= 500:
            return LogLevel.ERROR
        if status_code >= 400:
            return LogLevel.WARNING
        return LogLevel.INFO
