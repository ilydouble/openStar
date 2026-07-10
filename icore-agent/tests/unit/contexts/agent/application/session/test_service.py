"""Tests for the agent session application service."""

from datetime import UTC, datetime
from uuid import uuid4

from icore_agent.contexts.agent.application.session import AgentSessionService
from icore_agent.contexts.agent.domain.session import (
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.turn import Turn, TurnStatus


def test_search_user_sessions_empty_query_returns_no_results() -> None:
    """Blank search text should short-circuit without hitting the database."""
    service = AgentSessionService()

    payload = service.search_user_sessions("user-1", query="   ")

    assert payload == {
        "query": "",
        "sessions": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }


def test_search_user_sessions_clamps_pagination() -> None:
    """Search pagination bounds should mirror the list endpoint."""
    service = AgentSessionService()

    payload = service.search_user_sessions(
        "missing-user",
        query="hello",
        limit=500,
        offset=-3,
    )

    assert payload["limit"] == 100
    assert payload["offset"] == 0
    assert payload["query"] == "hello"
    assert payload["sessions"] == []
    assert payload["total"] == 0


def test_search_user_sessions_accepts_single_character_query() -> None:
    """Single-character queries should reach the repository without a minimum limit."""
    service = AgentSessionService()

    payload = service.search_user_sessions("missing-user", query="a")

    assert payload["query"] == "a"
    assert payload["sessions"] == []
    assert payload["total"] == 0


def test_chat_history_projects_user_message_file_uuid_metadata() -> None:
    """File UUID references should round-trip through canonical user items."""
    service = AgentSessionService()
    session_id = f"session-{uuid4()}"
    user_id = f"user-{uuid4()}"
    file_uuid = str(uuid4())
    turn = Turn(session_id=session_id)
    service.ensure_owned_session(
        session_id, user_id, title="Use uploaded file")
    service.start_turn(
        session_id,
        user_id,
        turn=turn,
        user_item=UserMessageItem(
            content=[UserInput(
                type=UserInputType.TEXT,
                text="Summarize this",
            )],
            metadata={"file_uuids": [file_uuid]},
        ),
        title="Use uploaded file",
    )
    service.complete_turn(
        session_id,
        user_id,
        turn_id=turn.id,
        status=TurnStatus.COMPLETED,
        error=None,
        completed_at=datetime.now(UTC),
        duration_ms=10,
        model="test-model",
        provider="test-provider",
        usage={"total_tokens": 1},
    )

    messages = service.load_messages(session_id, user_id)

    assert messages == [{
        "role": "user",
        "content": "Summarize this",
        "metadata": {"file_uuids": [file_uuid]},
    }]


def test_chat_history_projects_display_caption_metadata() -> None:
    """Display captions should round-trip through canonical user item persistence."""
    service = AgentSessionService()
    session_id = f"session-{uuid4()}"
    user_id = f"user-{uuid4()}"
    file_uuid = str(uuid4())
    service.ensure_owned_session(session_id, user_id, title="Analyze files")
    turn = Turn(session_id=session_id)
    service.start_turn(
        session_id,
        user_id,
        turn=turn,
        user_item=UserMessageItem(
            content=[UserInput(
                type=UserInputType.TEXT,
                text=(
                    "Please answer based on the images and data files "
                    "I uploaded."
                ),
            )],
            metadata={
                "file_uuids": [file_uuid],
                "display_caption": "Hello please analysis these files",
            },
        ),
        title="Analyze files",
    )
    service.complete_turn(
        session_id,
        user_id,
        turn_id=turn.id,
        status=TurnStatus.COMPLETED,
        error=None,
        completed_at=datetime.now(UTC),
        duration_ms=1,
        model="test-model",
        provider="test-provider",
        usage={"total_tokens": 1},
    )

    messages = service.load_messages(session_id, user_id)

    assert messages[0]["metadata"] == {
        "file_uuids": [file_uuid],
        "display_caption": "Hello please analysis these files",
    }
