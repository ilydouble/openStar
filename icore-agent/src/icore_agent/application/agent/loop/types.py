"""Shared types for prepared agent loop execution."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Protocol

from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.turn import TurnEvent


class PreparedAgentRunner(Protocol):
    """Prepared agent surface needed by the turn loop."""

    def __call__(self, prompt_envelope: PromptEnvelope) -> Any:
        """Run one prompt envelope through the prepared agent."""
        ...


class AgentToolEventBridge(Protocol):
    """Runtime-neutral bridge between agent callbacks and turn events."""

    def on_callback(self, **kwargs: Any) -> None:
        """Handle a provider runtime streaming callback."""
        ...

    def bound_to(
        self,
        *,
        emit: Callable[[TurnEvent], None],
        emit_assistant_delta: Callable[[str], None],
    ) -> AbstractContextManager[None]:
        """Bind event sinks while one prepared runner invocation is active."""
        ...
