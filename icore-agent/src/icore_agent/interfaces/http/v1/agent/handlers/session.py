"""Conversation session handlers."""

from __future__ import annotations

import asyncio

from fastapi import Depends, HTTPException, Query

from icore_agent.application.chat import ChatHistoryService
from icore_agent.infrastructure.memory.attachment_store import attachments
from icore_agent.infrastructure.memory.conversation import memory

from ...dependencies import get_chat_history_service, get_current_user
from ..schemas.session import (
    SessionListResponse,
    SessionSearchResponse,
    SessionStateResponse,
)


def _history_http_error(exc: Exception) -> HTTPException:
    """Map chat history domain errors to HTTP responses."""
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    raise exc


async def list_sessions(
    user: dict = Depends(get_current_user),
    chat_history: ChatHistoryService = Depends(get_chat_history_service),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SessionListResponse:
    """List chat sessions owned by the current user from PostgreSQL."""
    payload = chat_history.list_user_sessions(
        user["id"],
        limit=limit,
        offset=offset,
    )
    return SessionListResponse(**payload)


async def search_sessions(
    user: dict = Depends(get_current_user),
    chat_history: ChatHistoryService = Depends(get_chat_history_service),
    q: str = Query(default="", max_length=500),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SessionSearchResponse:
    """Search owned chat sessions by title and message content."""
    payload = chat_history.search_user_sessions(
        user["id"],
        query=q,
        limit=limit,
        offset=offset,
    )
    return SessionSearchResponse(**payload)


async def clear_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    chat_history: ChatHistoryService = Depends(get_chat_history_service),
) -> dict:
    """Clear conversation memory and attachments for an owned session."""
    try:
        chat_history.soft_delete_session(session_id, user["id"])
    except (PermissionError, LookupError) as exc:
        raise _history_http_error(exc) from exc
    await asyncio.gather(memory.clear(session_id), attachments.clear(session_id))
    return {"cleared": True, "session_id": session_id}


async def get_session_state(
    session_id: str,
    user: dict = Depends(get_current_user),
    chat_history: ChatHistoryService = Depends(get_chat_history_service),
) -> SessionStateResponse:
    """Read recent messages and attachments for an owned session."""
    try:
        chat_history.assert_owned_session(session_id, user["id"])
    except (PermissionError, LookupError) as exc:
        raise _history_http_error(exc) from exc

    summary, messages = await memory.get_context(session_id)
    if not messages:
        try:
            messages = chat_history.load_messages(session_id, user["id"])
            summary = summary or None
        except (PermissionError, LookupError) as exc:
            raise _history_http_error(exc) from exc

    att_list = await attachments.list_info(session_id)
    return SessionStateResponse(
        session_id=session_id,
        summary=summary or None,
        messages=messages,
        attachments=att_list,
    )
