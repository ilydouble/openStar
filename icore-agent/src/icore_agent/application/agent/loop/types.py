"""Shared types for prepared agent loop execution."""

from __future__ import annotations

from typing import Any, Protocol


class PreparedAgentRunner(Protocol):
    """Prepared agent surface needed by the turn loop."""

    messages: list[dict[str, Any]]

    def __call__(self, message: str) -> Any:
        """Run one user message through the prepared agent."""
        ...
