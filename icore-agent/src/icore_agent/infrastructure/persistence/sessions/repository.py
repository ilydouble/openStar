"""SQLAlchemy repository for persisted chat sessions and messages."""

from __future__ import annotations

from datetime import UTC, datetime
import time
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from .models import ChatMessage, ChatSession, LlmToolCall

_HEADLINE_OPTS = "MaxFragments=1, MaxWords=20, MinWords=6, StartSel=<mark>, StopSel=</mark>"


class SqlAlchemyChatHistoryRepository:
    """Persist and load chat sessions through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one transactional SQLAlchemy session."""
        self._session = session

    def get_session_by_public_id(self, public_id: str) -> ChatSession | None:
        """Load one session row by its external public id."""
        result = self._session.execute(
            select(ChatSession).where(ChatSession.public_id == public_id)
        )
        return result.scalar_one_or_none()

    def create_session(self, public_id: str, user_id: str, title: str = "") -> ChatSession:
        """Create a new owned chat session row."""
        now = int(time.time())
        row = ChatSession(
            public_id=public_id,
            user_id=user_id,
            title=title.strip()[:255],
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def reactivate_session(self, row: ChatSession, title: str = "") -> ChatSession:
        """Re-open a previously soft-deleted session for the same public id."""
        now = int(time.time())
        row.deleted_at = None
        row.updated_at = now
        if title.strip() and not row.title.strip():
            row.title = title.strip()[:255]
        self._session.flush()
        return row

    def touch_session(self, row: ChatSession) -> None:
        """Update the session updated_at timestamp."""
        row.updated_at = int(time.time())
        self._session.flush()

    def soft_delete_session(self, row: ChatSession) -> None:
        """Mark one session as deleted without removing message history."""
        now = int(time.time())
        row.deleted_at = now
        row.updated_at = now
        self._session.flush()

    def append_message(
        self,
        row: ChatSession,
        *,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """Append one message to a session with the next sequence number."""
        next_sequence = self._next_sequence(row.id)
        now = int(time.time())
        message = ChatMessage(
            session_id=row.id,
            role=role,
            content=content,
            sequence=next_sequence,
            created_at=now,
            message_metadata=dict(metadata or {}),
        )
        self._session.add(message)
        row.updated_at = now
        self._session.flush()
        return message

    def get_message(self, row: ChatSession, message_id: int) -> ChatMessage | None:
        """Load one message row that belongs to a chat session."""
        result = self._session.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == row.id,
            )
        )
        return result.scalar_one_or_none()

    def list_messages(self, row: ChatSession) -> list[ChatMessage]:
        """Return all messages for one session ordered by sequence."""
        result = self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == row.id)
            .order_by(ChatMessage.sequence.asc())
        )
        return list(result.scalars().all())

    def start_tool_call(
        self,
        row: ChatSession,
        *,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        tool_type: str = "function",
        started_at: datetime | None = None,
    ) -> LlmToolCall:
        """Persist the start of one LLM tool invocation."""
        existing = self.get_tool_call(row, tool_call_id)
        now = datetime.now(UTC)
        if existing is not None:
            existing.tool_name = tool_name
            existing.tool_type = tool_type
            existing.arguments = dict(arguments)
            existing.started_at = started_at or existing.started_at or now
            self._session.flush()
            return existing

        tool_call = LlmToolCall(
            session_id=row.id,
            assistant_message_id=None,
            tool_message_id=None,
            tool_call_id=tool_call_id,
            tool_type=tool_type,
            tool_name=tool_name,
            arguments=dict(arguments),
            result=None,
            status="running",
            error_code=None,
            error_message=None,
            elapsed_ms=None,
            created_at=now,
            started_at=started_at or now,
            finished_at=None,
        )
        self._session.add(tool_call)
        self._session.flush()
        return tool_call

    def get_tool_call(
        self,
        row: ChatSession,
        tool_call_id: str,
    ) -> LlmToolCall | None:
        """Load one tool call by Strands tool-use id within a session."""
        result = self._session.execute(
            select(LlmToolCall).where(
                LlmToolCall.session_id == row.id,
                LlmToolCall.tool_call_id == tool_call_id,
            )
        )
        return result.scalar_one_or_none()

    def finish_tool_call(
        self,
        tool_call: LlmToolCall,
        *,
        status: str,
        result: dict[str, Any] | None,
        error_code: str | None,
        error_message: str | None,
        elapsed_ms: int | None,
        finished_at: datetime | None = None,
        tool_message: ChatMessage | None = None,
        tool_message_id: int | None = None,
    ) -> LlmToolCall:
        """Persist the completed result for one tool invocation."""
        tool_call.status = status
        tool_call.result = result
        tool_call.error_code = error_code
        tool_call.error_message = error_message
        tool_call.elapsed_ms = elapsed_ms
        tool_call.finished_at = finished_at or datetime.now(UTC)
        if tool_message is not None:
            tool_call.tool_message_id = tool_message.id
        elif tool_message_id is not None:
            tool_call.tool_message_id = tool_message_id
        self._session.flush()
        return tool_call

    def link_tool_calls_to_assistant(
        self,
        row: ChatSession,
        *,
        tool_call_ids: tuple[str, ...],
        assistant_message: ChatMessage,
    ) -> None:
        """Attach completed tool-call records to the final assistant message."""
        if not tool_call_ids:
            return
        self._session.execute(
            update(LlmToolCall)
            .where(
                LlmToolCall.session_id == row.id,
                LlmToolCall.tool_call_id.in_(tool_call_ids),
            )
            .values(assistant_message_id=assistant_message.id)
        )
        self._session.flush()

    def list_tool_call_summaries_by_assistant_message(
        self,
        row: ChatSession,
        *,
        assistant_message_ids: tuple[int, ...],
    ) -> dict[int, list[dict[str, Any]]]:
        """Return frontend-safe tool-call summaries keyed by assistant message id."""
        if not assistant_message_ids:
            return {}
        result = self._session.execute(
            select(LlmToolCall)
            .where(
                LlmToolCall.session_id == row.id,
                LlmToolCall.assistant_message_id.in_(assistant_message_ids),
            )
            .order_by(LlmToolCall.created_at.asc(), LlmToolCall.id.asc())
        )
        summaries: dict[int, list[dict[str, Any]]] = {}
        for tool_call in result.scalars().all():
            if tool_call.assistant_message_id is None:
                continue
            summaries.setdefault(tool_call.assistant_message_id, []).append({
                "tool_call_id": tool_call.tool_call_id,
                "tool_name": tool_call.tool_name,
                "status": tool_call.status,
                "elapsed_ms": tool_call.elapsed_ms,
                "created_at": tool_call.created_at.isoformat(),
            })
        return summaries

    def list_sessions_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[ChatSession, int]], int]:
        """Return paginated active sessions and message counts for one user."""
        filters = (
            ChatSession.user_id == user_id,
            ChatSession.deleted_at.is_(None),
        )
        total_result = self._session.execute(
            select(func.count()).select_from(ChatSession).where(*filters)
        )
        total = int(total_result.scalar_one() or 0)
        message_count = func.count(ChatMessage.id).label("message_count")
        rows_result = self._session.execute(
            select(ChatSession, message_count)
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .where(*filters)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows_result.all()), total

    def search_sessions_for_user(
        self,
        user_id: str,
        *,
        query: str,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search owned sessions by title and message content using PostgreSQL FTS."""
        search_text = query.strip()
        if not search_text:
            return [], 0

        bind = self._session.get_bind()
        if bind.dialect.name != "postgresql":
            return [], 0

        params = {
            "user_id": user_id,
            "search_text": search_text,
            "headline_opts": _HEADLINE_OPTS,
            "limit": limit,
            "offset": offset,
        }
        count_result = self._session.execute(
            text(
                """
                WITH query AS (
                    SELECT plainto_tsquery('simple', :search_text) AS tsq
                )
                SELECT COUNT(*)
                FROM sessions s
                CROSS JOIN query q
                WHERE s.user_id = :user_id
                  AND s.deleted_at IS NULL
                  AND q.tsq <> ''::tsquery
                  AND (
                      to_tsvector('simple', s.title) @@ q.tsq
                      OR EXISTS (
                          SELECT 1
                          FROM messages m
                          WHERE m.session_id = s.id
                            AND to_tsvector('simple', m.content) @@ q.tsq
                      )
                  )
                """
            ),
            params,
        )
        total = int(count_result.scalar_one() or 0)
        if total == 0:
            return [], 0

        rows_result = self._session.execute(
            text(
                """
                WITH query AS (
                    SELECT plainto_tsquery('simple', :search_text) AS tsq
                ),
                ranked AS (
                    SELECT
                        s.public_id,
                        s.title,
                        s.updated_at,
                        GREATEST(
                            COALESCE(ts_rank(to_tsvector('simple', s.title), q.tsq), 0),
                            COALESCE(
                                (
                                    SELECT MAX(ts_rank(to_tsvector('simple', m.content), q.tsq))
                                    FROM messages m
                                    WHERE m.session_id = s.id
                                      AND to_tsvector('simple', m.content) @@ q.tsq
                                ),
                                0
                            )
                        ) AS rank,
                        COALESCE(
                            (
                                SELECT ts_headline(
                                    'simple', m.content, q.tsq, :headline_opts
                                )
                                FROM messages m
                                WHERE m.session_id = s.id
                                  AND to_tsvector('simple', m.content) @@ q.tsq
                                ORDER BY ts_rank(to_tsvector('simple', m.content), q.tsq) DESC
                                LIMIT 1
                            ),
                            ts_headline('simple', s.title, q.tsq, :headline_opts)
                        ) AS snippet
                    FROM sessions s
                    CROSS JOIN query q
                    WHERE s.user_id = :user_id
                      AND s.deleted_at IS NULL
                      AND q.tsq <> ''::tsquery
                      AND (
                          to_tsvector('simple', s.title) @@ q.tsq
                          OR EXISTS (
                              SELECT 1
                              FROM messages m
                              WHERE m.session_id = s.id
                                AND to_tsvector('simple', m.content) @@ q.tsq
                          )
                      )
                )
                SELECT public_id, title, updated_at, rank, snippet
                FROM ranked
                ORDER BY rank DESC, updated_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = [
            {
                "public_id": row.public_id,
                "title": row.title,
                "updated_at": int(row.updated_at),
                "rank": float(row.rank or 0),
                "snippet": str(row.snippet or ""),
            }
            for row in rows_result.all()
        ]
        return rows, total

    def _next_sequence(self, session_id: int) -> int:
        """Return the next message sequence number for one session."""
        result = self._session.execute(
            select(func.max(ChatMessage.sequence)).where(
                ChatMessage.session_id == session_id
            )
        )
        current = result.scalar_one_or_none()
        return int(current or 0) + 1
