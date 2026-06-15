from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from icore_agent.interfaces.http.v1.envelope import _wrap_success_response


def test_wrap_success_response_preserves_background_tasks() -> None:
    """ApiEnvelope wrapping must not drop Starlette background tasks."""
    request = MagicMock()
    request.url.path = "/api/v1/agent/session/demo/finalize"
    ran = {"value": False}

    def mark_ran() -> None:
        ran["value"] = True

    original = JSONResponse({"finalized": True, "session_id": "demo"})
    original.background = BackgroundTask(mark_ran)

    wrapped = _wrap_success_response(request, original)
    payload = json.loads(wrapped.body.decode("utf-8"))

    assert payload["data"]["finalized"] is True
    assert wrapped.background is original.background
    assert isinstance(wrapped.background, BackgroundTask)


@pytest.mark.asyncio
async def test_finalize_session_schedules_background_extract() -> None:
    """Finalize should return immediately and schedule extraction as a background task."""
    from icore_agent.interfaces.http.v1.agent.handlers import session as session_handlers

    user = MagicMock(public_id="user-1")
    agent_session = MagicMock()
    agent_session.assert_owned_session = MagicMock()
    user_memory_service = MagicMock()
    background_tasks = MagicMock()

    result = await session_handlers.finalize_session(
        "session-1",
        background_tasks,
        user=user,
        agent_session=agent_session,
        user_memory_service=user_memory_service,
    )

    agent_session.assert_owned_session.assert_called_once_with(
        "session-1", "user-1")
    background_tasks.add_task.assert_called_once_with(
        session_handlers._run_finalize_session_extract,
        user_id="user-1",
        session_id="session-1",
        agent_session=agent_session,
        user_memory_service=user_memory_service,
    )
    user_memory_service.extract_on_session_end.assert_not_called()
    assert result == {"finalized": True, "session_id": "session-1"}


@pytest.mark.asyncio
async def test_clear_session_schedules_background_extract() -> None:
    """Clear session should snapshot context, delete immediately, and schedule extract."""
    from icore_agent.interfaces.http.v1.agent.handlers import session as session_handlers

    user = MagicMock(public_id="user-1")
    agent_session = MagicMock()
    agent_session.assert_owned_session = MagicMock()
    agent_session.soft_delete_session = MagicMock()
    user_memory_service = MagicMock()
    background_tasks = MagicMock()
    session_handlers.memory = MagicMock()
    session_handlers.memory.clear = AsyncMock()
    session_handlers.resolve_session_extract_context = AsyncMock(
        return_value=("summary", [{"role": "user", "content": "hello"}]),
    )

    result = await session_handlers.clear_session(
        "session-1",
        background_tasks,
        user=user,
        agent_session=agent_session,
        user_memory_service=user_memory_service,
    )

    agent_session.assert_owned_session.assert_called_once_with(
        "session-1", "user-1")
    session_handlers.resolve_session_extract_context.assert_awaited_once()
    agent_session.soft_delete_session.assert_called_once_with(
        "session-1", "user-1")
    session_handlers.memory.clear.assert_awaited_once_with("session-1")
    background_tasks.add_task.assert_called_once_with(
        session_handlers._run_session_end_extract_from_context,
        user_id="user-1",
        session_id="session-1",
        session_summary="summary",
        recent_messages=[{"role": "user", "content": "hello"}],
        user_memory_service=user_memory_service,
    )
    user_memory_service.extract_on_session_end.assert_not_called()
    assert result == {"cleared": True, "session_id": "session-1"}
