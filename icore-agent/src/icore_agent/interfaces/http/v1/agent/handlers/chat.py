"""HTTP adapter for agent chat turns."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from icore_agent.application.agent import AgentTurnCommand, AgentTurnService
from icore_agent.application.agent.runtime import AgentRunConflict
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import get_agent_turn_service, get_current_user
from ...envelope import make_api_envelope
from ...streaming import sse_response
from ..schemas.chat import ChatRequest, ChatResponse

_UPGRADE_URL = "/pricing"


async def chat(
    req: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    agent_turn_service: AgentTurnService = Depends(get_agent_turn_service),
):
    """Translate one HTTP chat request into an application agent command."""
    command = _command_from_request(req, user)
    try:
        if req.stream:
            events = await agent_turn_service.stream(command)
            return sse_response(events, session_id=req.session_id)
        turn = await agent_turn_service.run(command)
    except PermissionError as exc:
        msg = str(exc)
        # Task-quota errors carry the "task_quota_exceeded:" prefix.
        # Return 402 so the frontend can show an upgrade modal instead of
        # a generic error, keeping the UX upgrade funnel intact.
        if msg.startswith("task_quota_exceeded:"):
            return JSONResponse(
                status_code=402,
                content=make_api_envelope(
                    code=402,
                    message="本月免费任务次数已用完，请升级套餐继续使用。",
                    data={
                        "upgrade_url": _UPGRADE_URL,
                        "current_plan": user.plan,
                    },
                    error_reason="quota_exceeded",
                ),
            )
        raise HTTPException(status_code=403, detail=msg) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(session_id=turn.session_id, reply=turn.reply_text())


def _command_from_request(req: ChatRequest, user: AuthenticatedUser) -> AgentTurnCommand:
    """Build an application command from validated HTTP request data."""
    return AgentTurnCommand(
        message=req.message,
        session_id=req.session_id,
        stream=req.stream,
        tenant_code=req.tenant_code,
        file_uuids=tuple(req.file_uuids),
        display_caption=(req.display_caption or "").strip() or None,
        agent_message=(req.agent_message or "").strip() or None,
        template_id=(req.template_id or "").strip() or None,
        incognito=req.incognito,
        user=user,
    )
