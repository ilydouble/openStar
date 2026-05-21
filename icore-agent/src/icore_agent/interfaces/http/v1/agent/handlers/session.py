"""Conversation session handlers."""

from fastapi import Depends

from icore_agent.infrastructure.memory.conversation import memory

from ...dependencies import get_current_user
from ..schemas.session import SessionStateResponse


async def clear_session(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Clear conversation memory for a session."""
    _ = user
    await memory.clear(session_id)
    return {"cleared": True, "session_id": session_id}


async def get_session_state(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> SessionStateResponse:
    """Read recent messages for a session."""
    _ = user
    summary, messages = await memory.get_context(session_id)
    return SessionStateResponse(
        session_id=session_id,
        summary=summary or None,
        messages=messages,
        attachments=[],
    )
