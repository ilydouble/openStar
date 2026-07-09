"""Agent API router."""

from fastapi import APIRouter

from icore_agent.interfaces.http.v1.envelope import ApiEnvelopeRoute
from .handlers import (
    abort_session_run,
    chat,
    clear_session,
    finalize_session,
    follow_up_session_run,
    get_session_state,
    list_sessions,
    search_sessions,
    steer_session_run,
    transcribe_audio,
)
from .schemas import (
    AgentRuntimeControlResponse,
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
    "/sessions/{session_id}/abort",
    response_model=AgentRuntimeControlResponse,
    summary="Abort the active agent run for a session",
)(abort_session_run)
router.post(
    "/sessions/{session_id}/steer",
    response_model=AgentRuntimeControlResponse,
    summary="Queue steering input for the active agent run",
)(steer_session_run)
router.post(
    "/sessions/{session_id}/follow-up",
    response_model=AgentRuntimeControlResponse,
    summary="Queue follow-up input for a later turn",
)(follow_up_session_run)
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
    summary="Read canonical turns and items for a session",
)(get_session_state)
