"""Tests for canonical turn and session-item persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ContextItem,
    SessionItemStatus,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.contexts.agent.domain.turn import Turn, TurnEvent, TurnEventKind, TurnStatus
from icore_agent.contexts.agent.infrastructure.persistence.sessions.models import (
    ChatSessionEvent,
    ChatSessionItem,
    ChatTurn,
)
from icore_agent.contexts.agent.infrastructure.persistence.sessions.repository import (
    SqlAlchemyChatHistoryRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.models import Base


def test_repository_metadata_excludes_legacy_message_and_tool_call_tables() -> None:
    """Canonical metadata should not expose legacy chat projection tables."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    assert "messages" not in Base.metadata.tables
    assert "llm_tool_calls" not in Base.metadata.tables


def test_repository_persists_tool_call_as_session_item() -> None:
    """Tool calls should be stored only as canonical ToolCallItem payloads."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    started_at = datetime.now(UTC)
    finished_at = datetime.now(UTC)

    with Session(engine) as session:
        repo = SqlAlchemyChatHistoryRepository(session)
        chat_session = repo.create_session(
            "session-public-id",
            "user-public-id",
            title="Use a tool",
        )
        turn = Turn(session_id="session-public-id")
        persisted_turn = repo.create_turn(chat_session, turn)
        repo.upsert_session_item(
            chat_session,
            persisted_turn,
            ToolCallItem(
                id="tool-item-1",
                provider_tool_call_id="tool-call-1",
                status=ToolCallStatus.RUNNING,
                function=ToolFunction(
                    name="web_search",
                    arguments_json={"query": "weather"},
                ),
                started_at=started_at,
            ),
        )
        repo.upsert_session_item(
            chat_session,
            persisted_turn,
            ToolCallItem(
                id="tool-item-1",
                provider_tool_call_id="tool-call-1",
                status=ToolCallStatus.COMPLETED,
                function=ToolFunction(
                    name="web_search",
                    arguments_json={"query": "weather"},
                ),
                result=ToolCallResult(
                    content="22C",
                    structured_content={"temperature": "22C"},
                ),
                started_at=started_at,
                completed_at=finished_at,
                duration_ms=12,
            ),
        )
        session.commit()

        stored_item = session.execute(select(ChatSessionItem)).scalar_one()

    assert stored_item.item_type == "tool_call"
    assert stored_item.payload["provider_tool_call_id"] == "tool-call-1"
    assert stored_item.payload["function"]["name"] == "web_search"
    assert stored_item.payload["function"]["arguments_json"] == {
        "query": "weather"}
    assert stored_item.payload["result"]["structured_content"] == {
        "temperature": "22C",
    }
    assert stored_item.payload["duration_ms"] == 12


def test_repository_persists_turn_context_user_item_and_usage() -> None:
    """Turn rows should store model metadata and ordered canonical items."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = SqlAlchemyChatHistoryRepository(session)
        chat_session = repo.create_session(
            "session-public-id",
            "user-public-id",
            title="Use a tool",
        )
        turn = Turn(
            session_id="session-public-id",
            model="test-model",
            provider="test-provider",
            usage={
                "prompt_tokens": 3,
                "completion_tokens": 4,
                "total_tokens": 7,
            },
        )
        persisted_turn = repo.create_turn(chat_session, turn)
        repo.upsert_session_item(
            chat_session,
            persisted_turn,
            ContextItem(kind="session_summary", content="Older summary"),
        )
        user_item = UserMessageItem(
            content=[UserInput(type=UserInputType.TEXT, text="Hello")],
            metadata={"file_uuids": ["file-1"]},
        )
        repo.upsert_session_item(chat_session, persisted_turn, user_item)
        repo.complete_turn(
            persisted_turn,
            status=TurnStatus.COMPLETED,
            error=None,
            completed_at=datetime.now(UTC),
            duration_ms=10,
            model=turn.model,
            provider=turn.provider,
            usage=turn.usage,
        )
        session.commit()

        stored_turn = session.execute(select(ChatTurn)).scalar_one()
        stored_items = session.execute(
            select(ChatSessionItem).order_by(ChatSessionItem.sequence.asc())
        ).scalars().all()

    assert stored_turn.public_id == turn.id
    assert stored_turn.status == "completed"
    assert stored_turn.duration_ms == 10
    assert stored_turn.model == "test-model"
    assert stored_turn.provider == "test-provider"
    assert stored_turn.usage == {
        "prompt_tokens": 3,
        "completion_tokens": 4,
        "total_tokens": 7,
    }
    assert [stored_item.item_type for stored_item in stored_items] == [
        "context",
        "user_message",
    ]
    assert stored_items[0].payload["content"] == "Older summary"
    assert stored_items[1].payload["content"][0]["text"] == "Hello"
    assert stored_items[1].payload["metadata"] == {"file_uuids": ["file-1"]}


def test_repository_appends_turn_events_for_replay_without_replacing_items() -> None:
    """Turn events should be append-only replay/debug records beside items."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = SqlAlchemyChatHistoryRepository(session)
        chat_session = repo.create_session(
            "session-public-id",
            "user-public-id",
            title="Events",
        )
        turn = Turn(session_id="session-public-id", id="turn-1")
        persisted_turn = repo.create_turn(chat_session, turn)
        event = TurnEvent(
            kind=TurnEventKind.ITEM_DELTA,
            session_id="session-public-id",
            turn_id="turn-1",
            item_id="assistant-1",
            delta={"text_append": "Hi"},
            event_id="event-1",
            seq=3,
            run_id="run-1",
        )

        repo.append_turn_event(chat_session, persisted_turn, event)
        session.commit()

        stored_event = session.execute(select(ChatSessionEvent)).scalar_one()
        stored_items = session.execute(select(ChatSessionItem)).scalars().all()

    assert stored_items == []
    assert stored_event.public_id == "event-1"
    assert stored_event.run_id == "run-1"
    assert stored_event.sequence == 3
    assert stored_event.event_type == "item_delta"
    assert stored_event.item_public_id == "assistant-1"
    assert stored_event.payload["delta"] == {"text_append": "Hi"}


def test_repository_projects_completed_turn_items_to_chat_history() -> None:
    """Legacy model history helpers should be rebuilt from completed session items."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = SqlAlchemyChatHistoryRepository(session)
        chat_session = repo.create_session(
            "session-public-id",
            "user-public-id",
            title="History",
        )
        completed = repo.create_turn(
            chat_session,
            Turn(session_id="session-public-id", status=TurnStatus.COMPLETED),
        )
        in_progress = repo.create_turn(
            chat_session,
            Turn(session_id="session-public-id"),
        )
        repo.upsert_session_item(
            chat_session,
            completed,
            UserMessageItem(
                content=[UserInput(type=UserInputType.TEXT,
                                   text="Old question")],
                metadata={"file_uuids": ["file-1"]},
            ),
        )
        repo.upsert_session_item(
            chat_session,
            completed,
            AgentMessageItem(
                status=SessionItemStatus.COMPLETED,
                text="Old answer",
            ),
        )
        repo.upsert_session_item(
            chat_session,
            in_progress,
            UserMessageItem(
                content=[UserInput(type=UserInputType.TEXT,
                                   text="Current question")],
            ),
        )
        history = repo.list_history_messages(chat_session)

    assert history == [
        {
            "role": "user",
            "content": "Old question",
            "metadata": {"file_uuids": ["file-1"]},
        },
        {
            "role": "assistant",
            "content": "Old answer",
            "metadata": {},
        },
    ]
