"""Tests for persisted LLM tool call records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from icore_agent.domain.chat import ChatCompletionRole
from icore_agent.domain.chat.session import UserInput, UserInputType, UserMessageItem
from icore_agent.domain.chat.turn import Turn, TurnStatus
from icore_agent.infrastructure.persistence.sessions.models import (
    ChatSessionItem,
    ChatTurn,
    LlmToolCall,
)
from icore_agent.infrastructure.persistence.sessions.repository import (
    SqlAlchemyChatHistoryRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.models import Base


def test_repository_persists_tool_call_and_links_messages() -> None:
    """Tool calls should link to internal session and persisted message rows."""
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
        tool_call = repo.start_tool_call(
            chat_session,
            tool_call_id="tool-call-1",
            tool_name="web_search",
            arguments={"query": "weather"},
            started_at=started_at,
        )
        tool_message = repo.append_message(
            chat_session,
            role=ChatCompletionRole.TOOL.value,
            content='{"temperature": "22C"}',
            metadata={"tool_call_id": "tool-call-1"},
        )
        repo.finish_tool_call(
            tool_call,
            status="success",
            result={"temperature": "22C"},
            error_code=None,
            error_message=None,
            elapsed_ms=12,
            finished_at=finished_at,
            tool_message=tool_message,
        )
        assistant_message = repo.append_message(
            chat_session,
            role=ChatCompletionRole.ASSISTANT.value,
            content="It is 22C.",
        )
        repo.link_tool_calls_to_assistant(
            chat_session,
            tool_call_ids=("tool-call-1",),
            assistant_message=assistant_message,
        )
        chat_session_id = chat_session.id
        assistant_message_id = assistant_message.id
        tool_message_id = tool_message.id
        session.commit()

        persisted = session.execute(select(LlmToolCall)).scalar_one()

    assert persisted.session_id == chat_session_id
    assert persisted.assistant_message_id == assistant_message_id
    assert persisted.tool_message_id == tool_message_id
    assert persisted.tool_call_id == "tool-call-1"
    assert persisted.tool_type == "function"
    assert persisted.tool_name == "web_search"
    assert persisted.arguments == {"query": "weather"}
    assert persisted.result == {"temperature": "22C"}
    assert persisted.status == "success"
    assert persisted.elapsed_ms == 12


def test_repository_lists_tool_call_summaries_by_assistant_message() -> None:
    """Session state should be able to attach tool-call summaries to assistant messages."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = SqlAlchemyChatHistoryRepository(session)
        chat_session = repo.create_session(
            "session-public-id",
            "user-public-id",
            title="Use a tool",
        )
        assistant_message = repo.append_message(
            chat_session,
            role=ChatCompletionRole.ASSISTANT.value,
            content="Done.",
        )
        tool_call = repo.start_tool_call(
            chat_session,
            tool_call_id="tool-call-1",
            tool_name="web_search",
            arguments={"query": "weather"},
            started_at=datetime.now(UTC),
        )
        repo.finish_tool_call(
            tool_call,
            status="success",
            result={"hidden": True},
            error_code=None,
            error_message=None,
            elapsed_ms=12,
            finished_at=datetime.now(UTC),
            tool_message=None,
        )
        repo.link_tool_calls_to_assistant(
            chat_session,
            tool_call_ids=("tool-call-1",),
            assistant_message=assistant_message,
        )
        summaries = repo.list_tool_call_summaries_by_assistant_message(
            chat_session,
            assistant_message_ids=(assistant_message.id,),
        )

    assert summaries == {
        assistant_message.id: [
            {
                "tool_call_id": "tool-call-1",
                "tool_name": "web_search",
                "status": "success",
                "elapsed_ms": 12,
                "created_at": tool_call.created_at.isoformat(),
            }
        ]
    }


def test_repository_persists_turn_and_session_item() -> None:
    """Turn state should persist separately from model transcript messages."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = SqlAlchemyChatHistoryRepository(session)
        chat_session = repo.create_session(
            "session-public-id",
            "user-public-id",
            title="Use a tool",
        )
        turn = Turn(session_id="session-public-id")
        persisted_turn = repo.create_turn(chat_session, turn)
        item = UserMessageItem(
            content=[
                UserInput(
                    type=UserInputType.TEXT,
                    text="Hello",
                )
            ],
        )
        repo.upsert_session_item(chat_session, persisted_turn, item)
        completed_item = item.model_copy(update={"completed_at": item.created_at})
        repo.upsert_session_item(chat_session, persisted_turn, completed_item)
        repo.complete_turn(
            persisted_turn,
            status=TurnStatus.COMPLETED,
            error=None,
            completed_at=datetime.now(UTC),
            duration_ms=10,
        )
        session.commit()

        stored_turn = session.execute(select(ChatTurn)).scalar_one()
        stored_item = session.execute(select(ChatSessionItem)).scalar_one()

    assert stored_turn.public_id == turn.id
    assert stored_turn.status == "completed"
    assert stored_turn.duration_ms == 10
    assert stored_item.public_id == item.id
    assert stored_item.sequence == 1
    assert stored_item.item_type == "user_message"
    assert stored_item.payload["content"][0]["text"] == "Hello"
