"""ASGI middleware that binds a request id to each inbound HTTP request."""

from __future__ import annotations

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..request_context import clear_request_id, set_request_id
from .request_id_management import REQUEST_ID_HEADER, resolve_request_id


class RequestIdMiddleware:
    """Resolve, store, and return a request id for every HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an ASGI application with request id propagation."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Attach request id context around one HTTP request lifecycle."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(Headers(scope=scope))
        scope.setdefault("state", {})["request_id"] = request_id
        token = set_request_id(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            clear_request_id(token)
