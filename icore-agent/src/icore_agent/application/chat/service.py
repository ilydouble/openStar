"""Application service for durable chat session history."""

from __future__ import annotations

from typing import Any

from icore_agent.infrastructure.persistence.sessions.repository import (
    SqlAlchemyChatHistoryRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import sync_session_scope


class ChatHistoryService:
    """Coordinate PostgreSQL chat persistence and ownership checks."""

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

    def save_user_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist one user message immediately at the start of a chat turn."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            repo.append_message(row, role="user", content=content, metadata=metadata)
            if not row.title.strip():
                row.title = content.strip()[:255]
                repo.touch_session(row)

    def save_assistant_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist one assistant message after a chat turn completes."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            repo.append_message(
                row,
                role="assistant",
                content=content,
                metadata=metadata,
            )

    def load_messages(self, public_id: str, user_id: str) -> list[dict[str, str]]:
        """Load persisted messages for one owned session."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            if row.user_id != user_id:
                raise PermissionError("Session access denied")
            return [
                {"role": message.role, "content": message.content}
                for message in repo.list_messages(row)
            ]

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
                    "message_count": int(message_count or 0),
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
