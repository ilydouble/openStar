"""SQLAlchemy repository for persisted chat sessions and messages."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .models import ChatMessage, ChatSession

_HEADLINE_OPTS = "MaxFragments=1, MaxWords=20, MinWords=6, StartSel=<mark>, StopSel=</mark>"
_SEARCH_LANG = "english"
_TITLE_RANK_BOOST = 2.0

_SESSION_SEARCH_QUERY_CTE = f"""
    WITH query AS (
        SELECT
            plainto_tsquery('{_SEARCH_LANG}', :search_text) AS tsq,
            :search_text AS raw_text
    )
"""

_SESSION_SEARCH_MATCH_SQL = f"""
    (
        to_tsvector('{_SEARCH_LANG}', s.title) @@ q.tsq
        OR s.title ILIKE '%' || q.raw_text || '%'
        OR EXISTS (
            SELECT 1
            FROM messages m
            WHERE m.session_id = s.id
              AND (
                  to_tsvector('{_SEARCH_LANG}', m.content) @@ q.tsq
                  OR m.content ILIKE '%' || q.raw_text || '%'
              )
        )
    )
"""

_SESSION_SEARCH_TITLE_SCORE_SQL = f"""
    (
        COALESCE(ts_rank(to_tsvector('{_SEARCH_LANG}', s.title), q.tsq), 0)
        + COALESCE(similarity(s.title, q.raw_text), 0)
        + CASE
            WHEN s.title ILIKE '%' || q.raw_text || '%' THEN 0.05
            ELSE 0
          END
    )
"""

_SESSION_SEARCH_MESSAGE_SCORE_SQL = f"""
    COALESCE(
        (
            SELECT MAX(
                COALESCE(ts_rank(to_tsvector('{_SEARCH_LANG}', m.content), q.tsq), 0)
                + COALESCE(similarity(m.content, q.raw_text), 0)
                + CASE
                    WHEN m.content ILIKE '%' || q.raw_text || '%' THEN 0.05
                    ELSE 0
                  END
            )
            FROM messages m
            WHERE m.session_id = s.id
              AND (
                  to_tsvector('{_SEARCH_LANG}', m.content) @@ q.tsq
                  OR m.content ILIKE '%' || q.raw_text || '%'
              )
        ),
        0
    )
"""

_SESSION_SEARCH_SNIPPET_SQL = f"""
    COALESCE(
        (
            SELECT ts_headline(
                '{_SEARCH_LANG}', m.content, q.tsq, :headline_opts
            )
            FROM messages m
            WHERE m.session_id = s.id
              AND to_tsvector('{_SEARCH_LANG}', m.content) @@ q.tsq
            ORDER BY ts_rank(to_tsvector('{_SEARCH_LANG}', m.content), q.tsq) DESC
            LIMIT 1
        ),
        (
            SELECT left(m.content, 200)
            FROM messages m
            WHERE m.session_id = s.id
              AND m.content ILIKE '%' || q.raw_text || '%'
            ORDER BY similarity(m.content, q.raw_text) DESC
            LIMIT 1
        ),
        ts_headline('{_SEARCH_LANG}', s.title, q.tsq, :headline_opts),
        s.title
    )
"""

_SESSION_SEARCH_RANK_SQL = f"""
    GREATEST(
        ({_SESSION_SEARCH_TITLE_SCORE_SQL}) * {_TITLE_RANK_BOOST},
        ({_SESSION_SEARCH_MESSAGE_SCORE_SQL})
    )
"""


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

    def list_messages(self, row: ChatSession) -> list[ChatMessage]:
        """Return all messages for one session ordered by sequence."""
        result = self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == row.id)
            .order_by(ChatMessage.sequence.asc())
        )
        return list(result.scalars().all())

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
        """Search owned sessions by title and message content using FTS and trigrams."""
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
                f"""
                {_SESSION_SEARCH_QUERY_CTE}
                SELECT COUNT(*)
                FROM sessions s
                CROSS JOIN query q
                WHERE s.user_id = :user_id
                  AND s.deleted_at IS NULL
                  AND {_SESSION_SEARCH_MATCH_SQL}
                """
            ),
            params,
        )
        total = int(count_result.scalar_one() or 0)
        if total == 0:
            return [], 0

        rows_result = self._session.execute(
            text(
                f"""
                {_SESSION_SEARCH_QUERY_CTE},
                ranked AS (
                    SELECT
                        s.public_id,
                        s.title,
                        s.updated_at,
                        ({_SESSION_SEARCH_RANK_SQL}) AS rank,
                        ({_SESSION_SEARCH_SNIPPET_SQL}) AS snippet
                    FROM sessions s
                    CROSS JOIN query q
                    WHERE s.user_id = :user_id
                      AND s.deleted_at IS NULL
                      AND {_SESSION_SEARCH_MATCH_SQL}
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
