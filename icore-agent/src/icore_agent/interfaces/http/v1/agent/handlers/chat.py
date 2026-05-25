"""HTTP adapter for agent chat turns."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from icore_agent.application.chat import ChatTurnCommand, ChatTurnService
from icore_agent.application.chat.routing import AgentHint
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import get_chat_turn_service, get_current_user
from ...streaming import sse_response
from ..schemas.chat import ChatRequest, ChatResponse


async def chat(
    req: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    chat_turn_service: ChatTurnService = Depends(get_chat_turn_service),
):
    """Translate one HTTP chat request into an application chat command."""
    command = _command_from_request(req, user)
    try:
        if req.stream:
            events = await chat_turn_service.stream(command)
            return sse_response(events, session_id=req.session_id)
        result = await chat_turn_service.run(command)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(session_id=result.session_id, reply=result.reply)


def _command_from_request(req: ChatRequest, user: AuthenticatedUser) -> ChatTurnCommand:
    """Build an application command from validated HTTP request data."""
    return ChatTurnCommand(
        message=req.message,
        session_id=req.session_id,
        stream=req.stream,
        tenant_code=req.tenant_code,
        agent_hint=_parse_agent_hint(req.agent_hint),
        file_uuids=tuple(req.file_uuids),
        display_caption=(req.display_caption or "").strip() or None,
        agent_message=(req.agent_message or "").strip() or None,
        template_id=(req.template_id or "").strip() or None,
        user=user,
    )


def _parse_agent_hint(value: str) -> AgentHint | None:
    """Convert an optional HTTP agent hint string into a typed enum."""
    hint = (value or "").strip().lower()
    if not hint:
        return None
    try:
        return AgentHint(hint)
    except ValueError:
        return None
