"""Request-scoped runtime user context."""

from __future__ import annotations

from contextvars import ContextVar

from icore_agent.contexts.account.domain.user import AuthenticatedUser

_runtime_user: ContextVar[AuthenticatedUser | None] = ContextVar(
    "runtime_user", default=None)


def set_runtime_user(user: AuthenticatedUser | None):
    """Set the request-scoped runtime user and return the reset token."""
    return _runtime_user.set(user)


def clear_runtime_user(token) -> None:
    """Reset the request-scoped runtime user with a token from set_runtime_user."""
    _runtime_user.reset(token)


def current_runtime_user() -> AuthenticatedUser | None:
    """Return the current request-scoped runtime user payload."""
    return _runtime_user.get()
