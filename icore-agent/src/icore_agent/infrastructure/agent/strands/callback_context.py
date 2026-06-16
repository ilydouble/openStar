"""Cross-agent Strands callback plumbing."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token

_PARENT_CALLBACK: ContextVar[Callable | None] = ContextVar(
    "icore_parent_callback", default=None
)


def set_parent_callback(cb: Callable | None) -> Token:
    """Install the parent agent callback for the current context."""
    return _PARENT_CALLBACK.set(cb)


def reset_parent_callback(token: Token) -> None:
    """Reset the parent agent callback to a previous context token."""
    _PARENT_CALLBACK.reset(token)


def sub_agent_callback() -> Callable | None:
    """Return a filtered callback that forwards only nested tool-use events."""
    parent = _PARENT_CALLBACK.get()
    if parent is None:
        return None

    def _filtered(**kwargs):
        """Forward nested Strands tool-use callbacks to the parent agent."""
        if kwargs.get("current_tool_use"):
            parent(**kwargs)

    return _filtered
