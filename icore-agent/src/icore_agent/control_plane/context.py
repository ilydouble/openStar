"""Request-scoped runtime user context."""

from __future__ import annotations

from contextvars import ContextVar

_runtime_user: ContextVar[dict | None] = ContextVar("runtime_user", default=None)


def set_runtime_user(user: dict | None):
    return _runtime_user.set(user)


def clear_runtime_user(token) -> None:
    _runtime_user.reset(token)


def current_runtime_user() -> dict | None:
    return _runtime_user.get()
