"""Application service for durable agent session history."""

from __future__ import annotations

from typing import Any

from icore_agent.domain.agent.session import SessionItem, UserMessageItem
from icore_agent.domain.agent.turn import Turn, TurnError, TurnStatus
from icore_agent.infrastructure.persistence.sessions.repository import (
    SqlAlchemyChatHistoryRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import sync_session_scope


class AgentSessionService:
    """Coordinate PostgreSQL-backed agent session persistence and ownership."""

    def ensure_owned_session(
        self,
        public_id: str,
        user_id: str,
        *,
        title: str = "",
    ) -> None:
        """Create a session or verify that the current user owns it."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None:
                repo.create_session(public_id, user_id, title=title)
                return
            if row.user_id != user_id:
                raise PermissionError("Session access denied")
            if row.deleted_at is not None:
                repo.reactivate_session(row, title=title)

    def assert_owned_session(self, public_id: str, user_id: str) -> None:
        """Verify that an existing active session belongs to the current user."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            if row.user_id != user_id:
                raise PermissionError("Session access denied")

    def start_turn(
        self,
        public_id: str,
        user_id: str,
        *,
        turn: Turn,
        user_item: UserMessageItem,
        title: str = "",
    ) -> None:
        """Persist one turn and its initial user message item atomically."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            persisted_turn = repo.create_turn(row, turn)
            repo.upsert_session_item(row, persisted_turn, user_item)
            if not row.title.strip():
                row.title = (title or user_item.to_text()).strip()[:255]
                repo.touch_session(row)

    def create_turn(self, public_id: str, user_id: str, turn: Turn) -> None:
        """Persist the start of one domain turn."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            repo.create_turn(row, turn)

    def upsert_session_item(
        self,
        public_id: str,
        user_id: str,
        *,
        turn_id: str,
        item: SessionItem,
    ) -> None:
        """Persist or update one domain item inside a turn."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            turn = repo.get_turn(row, turn_id)
            if turn is None:
                raise LookupError("Turn not found")
            repo.upsert_session_item(row, turn, item)

    def complete_turn(
        self,
        public_id: str,
        user_id: str,
        *,
        turn_id: str,
        status: TurnStatus,
        error: TurnError | None,
        completed_at,
        duration_ms: int | None,
        model: str | None = None,
        provider: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Persist the final state of one domain turn."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            turn = repo.get_turn(row, turn_id)
            if turn is None:
                raise LookupError("Turn not found")
            repo.complete_turn(
                turn,
                status=status,
                error=error,
                completed_at=completed_at,
                duration_ms=duration_ms,
                model=model,
                provider=provider,
                usage=usage,
            )

    def load_messages(
        self,
        public_id: str,
        user_id: str,
        *,
        include_tool_calls: bool = False,
        include_tool_messages: bool = False,
    ) -> list[dict[str, Any]]:
        """Project completed canonical items into user/assistant messages."""
        _ = include_tool_calls, include_tool_messages
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            if row.user_id != user_id:
                raise PermissionError("Session access denied")
            return repo.list_history_messages(row)

    def load_session_timeline(
        self,
        public_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Load canonical turns and session item payloads for one owned session."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            if row.user_id != user_id:
                raise PermissionError("Session access denied")
            return repo.list_session_timeline(row)

    def soft_delete_session(self, public_id: str, user_id: str) -> None:
        """Soft-delete one owned session while leaving message rows in place."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            if row.user_id != user_id:
                raise PermissionError("Session access denied")
            repo.soft_delete_session(row)

    def list_user_sessions(
        self,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return paginated session summaries for one user."""
        bounded_limit = max(min(limit, 100), 1)
        bounded_offset = max(offset, 0)
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            rows, total = repo.list_sessions_for_user(
                user_id,
                limit=bounded_limit,
                offset=bounded_offset,
            )
            sessions = [
                {
                    "title": chat_session.title,
                    "public_id": chat_session.public_id,
                    "created_at": int(chat_session.created_at),
                    "updated_at": int(chat_session.updated_at),
                    "turn_count": int(message_count or 0),
                }
                for chat_session, message_count in rows
            ]
        return {
            "sessions": sessions,
            "total": total,
            "limit": bounded_limit,
            "offset": bounded_offset,
        }

    def search_user_sessions(
        self,
        user_id: str,
        *,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search owned sessions by title and message content."""
        bounded_limit = max(min(limit, 100), 1)
        bounded_offset = max(offset, 0)
        search_text = query.strip()
        if not search_text:
            return {
                "query": "",
                "sessions": [],
                "total": 0,
                "limit": bounded_limit,
                "offset": bounded_offset,
            }
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            rows, total = repo.search_sessions_for_user(
                user_id,
                query=search_text,
                limit=bounded_limit,
                offset=bounded_offset,
            )
            sessions = [
                {
                    "title": row["title"],
                    "public_id": row["public_id"],
                    "updated_at": int(row["updated_at"]),
                    "rank": float(row["rank"]),
                    "snippet": row["snippet"],
                }
                for row in rows
            ]
        return {
            "query": search_text,
            "sessions": sessions,
            "total": total,
            "limit": bounded_limit,
            "offset": bounded_offset,
        }
