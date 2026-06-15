"""Application commands for agent turn workflows."""

from __future__ import annotations

from dataclasses import dataclass

from icore_agent.domain.user import AuthenticatedUser


@dataclass(frozen=True, slots=True)
class AgentTurnCommand:
    """Command object for one authenticated agent turn."""

    message: str
    session_id: str
    stream: bool
    tenant_code: str
    file_uuids: tuple[str, ...]
    display_caption: str | None
    agent_message: str | None
    template_id: str | None
    incognito: bool
    user: AuthenticatedUser
    pi_workspace_id: str | None = None

    @property
    def user_id(self) -> str:
        """Return the authenticated public user id."""
        return self.user.public_id
