"""Text attachment handlers."""

from typing import Annotated

from fastapi import Depends, File, Form, HTTPException, UploadFile

from icore_agent.application.account import AccountService
from icore_agent.application.knowledge import SUPPORTED_EXTENSIONS, parse_file
from icore_agent.config import settings
from icore_agent.infrastructure.memory.attachment_store import attachments
from icore_agent.shared.logging.app_logger import get_logger

from ...dependencies import get_account_service, get_current_user
from ..schemas.attachment import AttachmentInfo, AttachResponse

log = get_logger(__name__)


async def attach_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT, or MD file")],
    session_id: Annotated[str, Form(description="Session ID to attach the document to")],
    user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service),
) -> AttachResponse:
    """Upload a text document and attach it to a chat session context."""
    allowed, reason = account_service.check_quota(user["id"], "attachments")
    if not allowed:
        raise HTTPException(status_code=402, detail=reason)
    ext = "." + file.filename.rsplit(".", 1)[-1].lower(
    ) if file.filename and "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )
    data = await file.read()
    if len(data) > settings.file_ops_max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.file_ops_max_size_mb} MB limit",
        )
    try:
        text = parse_file(file.filename or "upload", data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse file: {exc}",
        ) from exc
    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="File appears to be empty or unreadable",
        )

    att = await attachments.add(session_id, file.filename or "upload", text)
    account_service.consume_quota(user["id"], "attachments")
    log.info(
        "attachment_added",
        session_id=session_id,
        filename=att["filename"],
        mode=att["mode"],
        chars=att["char_count"],
    )
    return AttachResponse(
        filename=att["filename"],
        char_count=att["char_count"],
        mode=att["mode"],
    )


async def list_attachments(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> list[AttachmentInfo]:
    """List documents attached to a chat session."""
    _ = user
    info = await attachments.list_info(session_id)
    return [AttachmentInfo(**a) for a in info]


async def remove_attachment(
    session_id: str,
    filename: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Remove a document attachment from a chat session."""
    _ = user
    removed = await attachments.remove(session_id, filename)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Attachment '{filename}' not found",
        )
    return {"removed": True, "filename": filename, "session_id": session_id}
