"""Conversation session handlers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query

from icore_agent.application.chat import ChatHistoryService
from icore_agent.application.files import FileAssetNotFoundError, FileAssetService
from icore_agent.infrastructure.memory.conversation import memory

from ...dependencies import (
    get_chat_history_service,
    get_current_user,
    get_file_asset_service,
)
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
    """Soft-delete an owned session and clear its cached conversation memory."""
    try:
        chat_history.soft_delete_session(session_id, user["id"])
    except (PermissionError, LookupError) as exc:
        raise _history_http_error(exc) from exc
    await memory.clear(session_id)
    return {"cleared": True, "session_id": session_id}


async def get_session_state(
    session_id: str,
    user: dict = Depends(get_current_user),
    chat_history: ChatHistoryService = Depends(get_chat_history_service),
    file_service: FileAssetService = Depends(get_file_asset_service),
) -> SessionStateResponse:
    """Read recent messages and file UUID attachments for an owned session."""
    try:
        chat_history.assert_owned_session(session_id, user["id"])
        persisted_messages = chat_history.load_messages(session_id, user["id"])
    except (PermissionError, LookupError) as exc:
        raise _history_http_error(exc) from exc

    summary, messages = await memory.get_context(session_id)
    if not messages:
        messages = persisted_messages
    return SessionStateResponse(
        session_id=session_id,
        summary=summary or None,
        messages=messages,
        attachments=_session_attachment_refs(
            persisted_messages,
            user_id=user["id"],
            file_service=file_service,
        ),
    )


def _session_attachment_refs(
    messages: list[dict],
    *,
    user_id: str,
    file_service: FileAssetService,
) -> list[dict]:
    """Resolve file UUIDs stored in message metadata into file asset references."""
    refs: list[dict] = []
    seen: set[str] = set()
    for message in messages:
        metadata = message.get("metadata")
        file_uuids = metadata.get("file_uuids") if isinstance(
            metadata, dict) else []
        if not isinstance(file_uuids, list):
            continue
        for raw_uuid in file_uuids:
            file_uuid = str(raw_uuid or "").strip()
            if not file_uuid or file_uuid in seen:
                continue
            seen.add(file_uuid)
            try:
                asset = file_service.get_owned_asset(
                    uploader_public_id=user_id,
                    file_uuid=file_uuid,
                )
            except FileAssetNotFoundError:
                continue
            item = {
                "file_uuid": asset.file_uuid,
                "original_filename": asset.original_filename,
                "filename": asset.original_filename,
                "content_type": asset.content_type,
                "mode": _asset_mode(asset.original_filename, asset.content_type),
            }
            if asset.content_type.startswith("image/"):
                item["download_url"] = file_service.create_download_url(
                    uploader_public_id=user_id,
                    file_uuid=asset.file_uuid,
                )
            refs.append(item)
    return refs


def _asset_mode(filename: str, content_type: str) -> str:
    """Return the frontend attachment mode for one file asset."""
    lower = filename.lower()
    if content_type.startswith("image/"):
        return "image"
    if lower.endswith((".csv", ".xlsx", ".xls")):
        return "data"
    return "file"
