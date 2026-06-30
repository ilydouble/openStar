"""Runtime control protocol for agent loop execution."""

from __future__ import annotations

from typing import Protocol

from icore_agent.domain.agent.session import UserMessageItem


class AgentLoopControl(Protocol):
    """Runtime control surface visible to the application agent loop."""

    async def abort_requested(self) -> bool:
        """Return whether the active run should abort cooperatively."""
        ...

    async def drain_steering(self) -> list[UserMessageItem]:
        """Drain runtime steering input for the current turn."""
        ...

    def run_id(self) -> str | None:
        """Return the active runtime run id when one exists."""
        ...


class NoopAgentLoopControl:
    """Default loop control used when no runtime shell is installed."""

    async def abort_requested(self) -> bool:
        """Return false because no runtime abort source exists."""
        return False

    async def drain_steering(self) -> list[UserMessageItem]:
        """Return no steering input."""
        return []

    def run_id(self) -> str | None:
        """Return no run id because no runtime shell is installed."""
        return None
