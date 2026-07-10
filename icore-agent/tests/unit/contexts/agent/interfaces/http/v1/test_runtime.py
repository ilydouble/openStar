"""Tests for HTTP agent runtime control handlers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from icore_agent.contexts.account.domain.user import AuthenticatedUser
from icore_agent.contexts.agent.application.runtime import (
    AgentRunControlResult,
    AgentRunNotActive,
)
from icore_agent.contexts.agent.interfaces.http.v1.handlers.runtime import (
    abort_session_run,
    follow_up_session_run,
    steer_session_run,
)
from icore_agent.contexts.agent.interfaces.http.v1.schemas.runtime import (
    AgentRuntimeInputRequest,
)


@pytest.mark.asyncio
async def test_steer_session_run_delegates_to_runtime_service() -> None:
    """Steering endpoint should enqueue current-turn user input."""
    service = FakeAgentRuntimeService()

    response = await steer_session_run(
        "session-1",
        AgentRuntimeInputRequest(message="Change direction."),
        user=_auth_user(),
        agent_turn_service=service,
    )

    assert response.accepted is True
    assert service.calls == [
        ("steer", "session-1", "user-1", "Change direction."),
    ]


@pytest.mark.asyncio
async def test_abort_session_run_returns_conflict_without_active_run() -> None:
    """Abort endpoint should return 409 when there is no active run."""
    service = FakeAgentRuntimeService(active=False)

    with pytest.raises(HTTPException) as exc:
        await abort_session_run(
            "session-1",
            user=_auth_user(),
            agent_turn_service=service,
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_follow_up_session_run_accepts_later_turn_input() -> None:
    """Follow-up endpoint should enqueue input for a later turn."""
    service = FakeAgentRuntimeService()

    response = await follow_up_session_run(
        "session-1",
        AgentRuntimeInputRequest(message="Next question."),
        user=_auth_user(),
        agent_turn_service=service,
    )

    assert response.accepted is True
    assert service.calls == [
        ("follow_up", "session-1", "user-1", "Next question."),
    ]


def _auth_user() -> AuthenticatedUser:
    """Build the authenticated domain user used by handler tests."""
    return AuthenticatedUser(
        public_id="user-1",
        email="user@example.com",
        name="User One",
        roles=("owner",),
    )


class FakeAgentRuntimeService:
    """Agent turn service fake exposing runtime control methods."""

    def __init__(self, *, active: bool = True) -> None:
        """Create the fake service."""
        self.active = active
        self.calls: list[tuple[str, str, str, str]] = []

    async def steer(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> AgentRunControlResult:
        """Record one steering request."""
        if not self.active:
            raise AgentRunNotActive("no active agent run")
        self.calls.append(("steer", session_id, user_id, message))
        return AgentRunControlResult(accepted=True, session_id=session_id)

    async def abort(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> AgentRunControlResult:
        """Record one abort request."""
        if not self.active:
            raise AgentRunNotActive("no active agent run")
        self.calls.append(("abort", session_id, user_id, ""))
        return AgentRunControlResult(accepted=True, session_id=session_id)

    async def follow_up(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> AgentRunControlResult:
        """Record one follow-up request."""
        self.calls.append(("follow_up", session_id, user_id, message))
        return AgentRunControlResult(accepted=True, session_id=session_id)
