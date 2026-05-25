"""Application commands for chat turn workflows."""

from __future__ import annotations

from dataclasses import dataclass

from icore_agent.domain.user import AuthenticatedUser

from .routing import AgentHint


@dataclass(frozen=True, slots=True)
class ChatTurnCommand:
    """Command object for one authenticated chat turn."""

    message: str
    session_id: str
    stream: bool
    tenant_code: str
    agent_hint: AgentHint | None
    file_uuids: tuple[str, ...]
    display_caption: str | None
    agent_message: str | None
    template_id: str | None
    user: AuthenticatedUser

    @property
    def user_id(self) -> str:
        """Return the authenticated public user id."""
        return self.user.public_id
