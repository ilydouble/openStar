"""Cross-agent callback plumbing.

The orchestrator exposes a Strands callback_handler that the SSE router uses
to observe tool invocations and forward them as `status` events to the UI.
Sub-agents (research / knowledge / image / data / code) create their own
internal Strands Agents, which by default isolate their callbacks — so inner
tool calls like `web_search`, `fetch_webpage`, `chroma_search` etc. stay
invisible to the outer router.

This module threads the orchestrator-level callback into sub-agent factories
via a ``contextvars.ContextVar``.  Sub-agents read a filtered wrapper that
forwards only ``current_tool_use`` events to the parent; the sub-agent's own
LLM token deltas must NOT leak, otherwise they would pollute the user-facing
assistant reply.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Callable, Optional

_PARENT_CALLBACK: ContextVar[Optional[Callable]] = ContextVar(
    "icore_parent_callback", default=None
)


def set_parent_callback(cb: Optional[Callable]) -> Token:
    """Install the orchestrator-level callback for the current context.

    Returns a token to pass to ``reset_parent_callback`` in a ``finally`` block.
    """
    return _PARENT_CALLBACK.set(cb)


def reset_parent_callback(token: Token) -> None:
    _PARENT_CALLBACK.reset(token)


def sub_agent_callback() -> Optional[Callable]:
    """Return a filtered callback to attach to a sub-agent, or ``None``.

    Forwards ``current_tool_use`` events to the parent (so the UI sees each
    inner tool call as a new ``status`` step); drops ``data`` / ``delta`` /
    lifecycle events so sub-agent tokens never mix into the orchestrator's
    streamed reply.
    """
    parent = _PARENT_CALLBACK.get()
    if parent is None:
        return None

    def _filtered(**kwargs):
        if kwargs.get("current_tool_use"):
            parent(**kwargs)

    return _filtered


__all__ = [
    "set_parent_callback",
    "reset_parent_callback",
    "sub_agent_callback",
]
