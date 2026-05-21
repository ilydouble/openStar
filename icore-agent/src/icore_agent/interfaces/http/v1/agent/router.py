"""Agent API router."""

from fastapi import APIRouter

from .handlers import (
    attach_data,
    attach_document,
    attach_image,
    chat,
    clear_session,
    get_image,
    get_session_state,
    list_attachments,
    remove_attachment,
    run_sequential,
    transcribe_audio,
)
from .schemas import (
    AttachmentInfo,
    AttachResponse,
    DataAttachResponse,
    ImageAttachResponse,
    SequentialResponse,
    SessionStateResponse,
    TranscribeResponse,
)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

router.post("/chat", summary="Chat with the agent (SSE streaming)")(
    chat
)
router.post(
    "/sequential",
    response_model=SequentialResponse,
    summary="Run a sequential bash task (mini-SWE-agent style)",
)(run_sequential)
router.post(
    "/attach",
    response_model=AttachResponse,
    summary="Upload a document and attach it to the session context",
)(attach_document)
router.get(
    "/attachments/{session_id}",
    response_model=list[AttachmentInfo],
    summary="List documents attached to a session",
)(list_attachments)
router.delete(
    "/attachments/{session_id}/{filename}",
    summary="Remove a document from session context",
)(remove_attachment)
router.post(
    "/attach/image",
    response_model=ImageAttachResponse,
    summary="Upload an image (jpg/png/webp) and attach it to the session",
)(attach_image)
router.get(
    "/images/{session_id}/{filename}",
    summary="Serve a session-scoped image",
)(get_image)
router.post(
    "/attach/data",
    response_model=DataAttachResponse,
    summary="Upload a CSV / Excel file to the session workspace for pandas analysis",
)(attach_data)
router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="Transcribe audio with Z.AI GLM-ASR",
)(transcribe_audio)
router.delete(
    "/session/{session_id}",
    summary="Clear conversation memory for a session",
)(clear_session)
router.get(
    "/session/{session_id}",
    response_model=SessionStateResponse,
    summary="Read recent messages and attachments for a session",
)(get_session_state)
