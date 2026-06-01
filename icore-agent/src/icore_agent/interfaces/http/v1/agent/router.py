"""Agent API router."""

from fastapi import APIRouter

from ..envelope import ApiEnvelopeRoute
from .handlers import (
    chat,
    clear_session,
    finalize_session,
    get_session_state,
    list_sessions,
    search_sessions,
    run_sequential,
    transcribe_audio,
)
from .schemas import (
    SequentialResponse,
    SessionListResponse,
    SessionSearchResponse,
    SessionStateResponse,
    TranscribeResponse,
)

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["agent"],
    route_class=ApiEnvelopeRoute,
)

router.post("/chat", summary="Chat with the agent (SSE streaming)")(
    chat
)
router.post(
    "/sequential",
    response_model=SequentialResponse,
    summary="Run a sequential bash task (mini-SWE-agent style)",
)(run_sequential)
router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="Transcribe audio with Z.AI GLM-ASR",
)(transcribe_audio)
router.delete(
    "/session/{session_id}",
    summary="Clear conversation memory for a session",
)(clear_session)
router.post(
    "/session/{session_id}/finalize",
    summary="Extract durable user memory when a session ends",
)(finalize_session)
router.get(
    "/sessions/search",
    response_model=SessionSearchResponse,
    summary="Search chat sessions by title and message content",
)(search_sessions)
router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List chat sessions for the current user",
)(list_sessions)
router.get(
    "/session/{session_id}",
    response_model=SessionStateResponse,
    summary="Read recent messages for a session",
)(get_session_state)
