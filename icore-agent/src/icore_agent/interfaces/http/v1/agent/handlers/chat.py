"""HTTP adapter for agent chat turns."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from icore_agent.application.chat import ChatTurnCommand, ChatTurnService
from icore_agent.application.chat.routing import AgentHint
from icore_agent.config import settings
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import get_chat_turn_service, get_current_user
from ...streaming import sse_response
from ..schemas.chat import ChatRequest, ChatResponse

_UPGRADE_URL = "/pricing"


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
        msg = str(exc)
        # Quota-exhausted errors start with "token_quota_exceeded:" prefix.
        # Return 402 so the frontend can distinguish "upgrade needed" from
        # regular 403 access-denied errors and show an upgrade modal.
        if msg.startswith("token_quota_exceeded:"):
            return JSONResponse(
                status_code=402,
                content={
                    "code": 402,
                    "error_code": "quota_exceeded",
                    "message": "您的 Token 配额已用尽，请升级套餐继续使用。",
                    "data": {
                        "upgrade_url": _UPGRADE_URL,
                        "current_plan": user.plan,
                    },
                },
            )
        raise HTTPException(status_code=403, detail=msg) from exc
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
