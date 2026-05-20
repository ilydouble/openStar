"""Request-scoped context values shared by HTTP middleware and service clients."""

from __future__ import annotations

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Return the request id bound to the current context, if one exists."""
    return _request_id.get()


def set_request_id(request_id: str | None) -> Token[str | None]:
    """Bind a request id to the current context and return its reset token."""
    return _request_id.set(request_id)


def clear_request_id(token: Token[str | None]) -> None:
    """Restore the previous request id context using a token from set_request_id."""
    _request_id.reset(token)
