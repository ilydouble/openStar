"""HTTP handlers for active agent runtime control."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from icore_agent.contexts.agent.application import AgentTurnService
from icore_agent.contexts.agent.application.runtime import AgentRunNotActive
from icore_agent.domain.user import AuthenticatedUser

from icore_agent.interfaces.http.v1.dependencies import (
    get_agent_turn_service,
    get_current_user,
)
from ..schemas.runtime import (
    AgentRuntimeControlResponse,
    AgentRuntimeInputRequest,
)


async def abort_session_run(
    session_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    agent_turn_service: AgentTurnService = Depends(get_agent_turn_service),
) -> AgentRuntimeControlResponse:
    """Request cooperative abort for the active run in one session."""
    try:
        result = await agent_turn_service.abort(
            session_id=session_id,
            user_id=user.public_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentRunNotActive as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentRuntimeControlResponse(**result.model_dump())


async def steer_session_run(
    session_id: str,
    req: AgentRuntimeInputRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    agent_turn_service: AgentTurnService = Depends(get_agent_turn_service),
) -> AgentRuntimeControlResponse:
    """Queue current-turn steering input for the active run."""
    try:
        result = await agent_turn_service.steer(
            session_id=session_id,
            user_id=user.public_id,
            message=req.message,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentRunNotActive as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentRuntimeControlResponse(**result.model_dump())


async def follow_up_session_run(
    session_id: str,
    req: AgentRuntimeInputRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    agent_turn_service: AgentTurnService = Depends(get_agent_turn_service),
) -> AgentRuntimeControlResponse:
    """Queue follow-up input for a later turn boundary."""
    try:
        result = await agent_turn_service.follow_up(
            session_id=session_id,
            user_id=user.public_id,
            message=req.message,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AgentRuntimeControlResponse(**result.model_dump())
