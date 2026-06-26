"""Application service for durable agent session history."""

from __future__ import annotations

from typing import Any

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.session import SessionItem
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

    def save_user_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Persist one user message immediately at the start of a chat turn."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            message = repo.append_message(
                row,
                role=ChatCompletionRole.USER.value,
                content=content,
                metadata=metadata,
            )
            if not row.title.strip():
                row.title = content.strip()[:255]
                repo.touch_session(row)
            return int(message.id)

    def save_assistant_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Persist one assistant message after a chat turn completes."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            message = repo.append_message(
                row,
                role=ChatCompletionRole.ASSISTANT.value,
                content=content,
                metadata=metadata,
            )
            return int(message.id)

    def save_tool_message(
        self,
        public_id: str,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Persist one tool result message after a tool invocation completes."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None or row.user_id != user_id:
                raise LookupError("Session not found")
            message = repo.append_message(
                row,
                role=ChatCompletionRole.TOOL.value,
                content=content,
                metadata=metadata,
            )
            return int(message.id)

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
            )

    def start_tool_call(
        self,
        public_id: str,
        *,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Persist the start of one tool call for an existing session."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            repo.start_tool_call(
                row,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments=arguments,
            )

    def finish_tool_call(
        self,
        public_id: str,
        *,
        tool_call_id: str,
        status: str,
        result: dict[str, Any] | None,
        error_code: str | None,
        error_message: str | None,
        elapsed_ms: int | None,
        tool_message_id: int | None,
    ) -> None:
        """Persist the final state and result for one tool call."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            tool_call = repo.get_tool_call(row, tool_call_id)
            if tool_call is None:
                tool_call = repo.start_tool_call(
                    row,
                    tool_call_id=tool_call_id,
                    tool_name="unknown",
                    arguments={},
                )
            repo.finish_tool_call(
                tool_call,
                status=status,
                result=result,
                error_code=error_code,
                error_message=error_message,
                elapsed_ms=elapsed_ms,
                tool_message_id=tool_message_id,
            )

    def attach_tool_calls_to_assistant(
        self,
        public_id: str,
        *,
        tool_call_ids: tuple[str, ...],
        assistant_message_id: int,
    ) -> None:
        """Link a completed assistant message to all tool calls from the turn."""
        if not tool_call_ids:
            return
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            assistant_message = repo.get_message(row, assistant_message_id)
            if assistant_message is None:
                raise LookupError("Assistant message not found")
            repo.link_tool_calls_to_assistant(
                row,
                tool_call_ids=tool_call_ids,
                assistant_message=assistant_message,
            )

    def load_messages(
        self,
        public_id: str,
        user_id: str,
        *,
        include_tool_calls: bool = False,
        include_tool_messages: bool = False,
    ) -> list[dict[str, Any]]:
        """Load persisted messages for one owned session."""
        with sync_session_scope() as session:
            repo = SqlAlchemyChatHistoryRepository(session)
            row = repo.get_session_by_public_id(public_id)
            if row is None or row.deleted_at is not None:
                raise LookupError("Session not found")
            if row.user_id != user_id:
                raise PermissionError("Session access denied")
            messages = [
                message
                for message in repo.list_messages(row)
                if include_tool_messages
                or message.role != ChatCompletionRole.TOOL.value
            ]
            assistant_ids = tuple(
                int(message.id)
                for message in messages
                if message.role == ChatCompletionRole.ASSISTANT.value
            )
            tool_calls_by_message = (
                repo.list_tool_call_summaries_by_assistant_message(
                    row,
                    assistant_message_ids=assistant_ids,
                )
                if include_tool_calls
                else {}
            )
            payload = []
            for message in messages:
                item = {
                    "role": message.role,
                    "content": message.content,
                    "metadata": dict(message.message_metadata or {}),
                }
                if include_tool_calls and message.id in tool_calls_by_message:
                    item["tool_calls"] = tool_calls_by_message[int(message.id)]
                payload.append(item)
            return payload

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
