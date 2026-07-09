"""SQLAlchemy repository for canonical agent sessions, turns, and items."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from icore_agent.contexts.agent.domain import ChatCompletionRole
from icore_agent.contexts.agent.domain.session import SessionItem
from icore_agent.contexts.agent.domain.turn import Turn, TurnError, TurnEvent, TurnStatus

from .models import ChatSession, ChatSessionEvent, ChatSessionItem, ChatTurn

_HEADLINE_OPTS = "MaxFragments=1, MaxWords=20, MinWords=6, StartSel=<mark>, StopSel=</mark>"
_SEARCH_LANG = "english"
_TITLE_RANK_BOOST = 2.0
_SEARCHABLE_ITEM_TYPES = ("user_message", "agent_message")

_SESSION_SEARCH_QUERY_CTE = f"""
    WITH query AS (
        SELECT
            plainto_tsquery('{_SEARCH_LANG}', :search_text) AS tsq,
            :search_text AS raw_text
    )
"""

_SESSION_ITEM_TEXT_SQL = "si.payload::text"

_SESSION_SEARCH_MATCH_SQL = f"""
    (
        to_tsvector('{_SEARCH_LANG}', s.title) @@ q.tsq
        OR s.title ILIKE '%' || q.raw_text || '%'
        OR EXISTS (
            SELECT 1
            FROM session_items si
            WHERE si.session_id = s.id
              AND si.item_type IN ('user_message', 'agent_message')
              AND (
                  to_tsvector('{_SEARCH_LANG}', {_SESSION_ITEM_TEXT_SQL}) @@ q.tsq
                  OR {_SESSION_ITEM_TEXT_SQL} ILIKE '%' || q.raw_text || '%'
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

_SESSION_SEARCH_ITEM_SCORE_SQL = f"""
    COALESCE(
        (
            SELECT MAX(
                COALESCE(ts_rank(to_tsvector('{_SEARCH_LANG}', {_SESSION_ITEM_TEXT_SQL}), q.tsq), 0)
                + COALESCE(similarity({_SESSION_ITEM_TEXT_SQL}, q.raw_text), 0)
                + CASE
                    WHEN {_SESSION_ITEM_TEXT_SQL} ILIKE '%' || q.raw_text || '%' THEN 0.05
                    ELSE 0
                  END
            )
            FROM session_items si
            WHERE si.session_id = s.id
              AND si.item_type IN ('user_message', 'agent_message')
              AND (
                  to_tsvector('{_SEARCH_LANG}', {_SESSION_ITEM_TEXT_SQL}) @@ q.tsq
                  OR {_SESSION_ITEM_TEXT_SQL} ILIKE '%' || q.raw_text || '%'
              )
        ),
        0
    )
"""

_SESSION_SEARCH_SNIPPET_SQL = f"""
    COALESCE(
        (
            SELECT ts_headline(
                '{_SEARCH_LANG}', {_SESSION_ITEM_TEXT_SQL}, q.tsq, :headline_opts
            )
            FROM session_items si
            WHERE si.session_id = s.id
              AND si.item_type IN ('user_message', 'agent_message')
              AND to_tsvector('{_SEARCH_LANG}', {_SESSION_ITEM_TEXT_SQL}) @@ q.tsq
            ORDER BY ts_rank(to_tsvector('{_SEARCH_LANG}', {_SESSION_ITEM_TEXT_SQL}), q.tsq) DESC
            LIMIT 1
        ),
        (
            SELECT left({_SESSION_ITEM_TEXT_SQL}, 200)
            FROM session_items si
            WHERE si.session_id = s.id
              AND si.item_type IN ('user_message', 'agent_message')
              AND {_SESSION_ITEM_TEXT_SQL} ILIKE '%' || q.raw_text || '%'
            ORDER BY similarity({_SESSION_ITEM_TEXT_SQL}, q.raw_text) DESC
            LIMIT 1
        ),
        ts_headline('{_SEARCH_LANG}', s.title, q.tsq, :headline_opts),
        s.title
    )
"""

_SESSION_SEARCH_RANK_SQL = f"""
    GREATEST(
        ({_SESSION_SEARCH_TITLE_SCORE_SQL}) * {_TITLE_RANK_BOOST},
        ({_SESSION_SEARCH_ITEM_SCORE_SQL})
    )
"""


class SqlAlchemyChatHistoryRepository:
    """Persist and load canonical agent session timeline state."""

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
        """Mark one session as deleted without removing timeline history."""
        now = int(time.time())
        row.deleted_at = now
        row.updated_at = now
        self._session.flush()

    def create_turn(self, row: ChatSession, turn: Turn) -> ChatTurn:
        """Persist one new execution turn for a session."""
        existing = self.get_turn(row, turn.id)
        if existing is not None:
            return existing
        chat_turn = ChatTurn(
            session_id=row.id,
            public_id=turn.id,
            status=_enum_value(turn.status),
            error=(
                turn.error.model_dump(mode="json")
                if turn.error is not None
                else None
            ),
            started_at=turn.started_at,
            completed_at=turn.completed_at,
            duration_ms=turn.duration_ms,
            model=turn.model,
            provider=turn.provider,
            usage=turn.usage,
        )
        self._session.add(chat_turn)
        row.updated_at = int(time.time())
        self._session.flush()
        return chat_turn

    def get_turn(self, row: ChatSession, turn_public_id: str) -> ChatTurn | None:
        """Load one turn by public id within a session."""
        result = self._session.execute(
            select(ChatTurn).where(
                ChatTurn.session_id == row.id,
                ChatTurn.public_id == turn_public_id,
            )
        )
        return result.scalar_one_or_none()

    def upsert_session_item(
        self,
        row: ChatSession,
        turn: ChatTurn,
        item: SessionItem,
    ) -> ChatSessionItem:
        """Insert or update one domain item for a turn."""
        payload = item.model_dump(mode="json")
        existing = self._session.execute(
            select(ChatSessionItem).where(
                ChatSessionItem.turn_id == turn.id,
                ChatSessionItem.public_id == item.id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.item_type = str(payload["type"])
            existing.status = str(payload["status"])
            existing.payload = payload
            existing.started_at = _item_started_at(item)
            existing.completed_at = _item_completed_at(item)
            row.updated_at = int(time.time())
            self._session.flush()
            return existing

        session_item = ChatSessionItem(
            session_id=row.id,
            turn_id=turn.id,
            public_id=item.id,
            item_type=str(payload["type"]),
            status=str(payload["status"]),
            sequence=self._next_turn_item_sequence(turn.id),
            payload=payload,
            started_at=_item_started_at(item),
            completed_at=_item_completed_at(item),
        )
        self._session.add(session_item)
        row.updated_at = int(time.time())
        self._session.flush()
        return session_item

    def append_turn_event(
        self,
        row: ChatSession,
        turn: ChatTurn,
        event: TurnEvent,
    ) -> ChatSessionEvent:
        """Append one public turn-stream event for replay and debugging."""
        existing = self._session.execute(
            select(ChatSessionEvent).where(
                ChatSessionEvent.turn_id == turn.id,
                ChatSessionEvent.public_id == event.event_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        event_row = ChatSessionEvent(
            session_id=row.id,
            turn_id=turn.id,
            public_id=event.event_id,
            run_id=event.run_id,
            sequence=int(event.seq or self._next_turn_event_sequence(turn.id)),
            event_type=_enum_value(event.kind),
            item_public_id=event.item_id,
            payload=event.to_payload(),
            created_at=event.created_at,
        )
        self._session.add(event_row)
        row.updated_at = int(time.time())
        self._session.flush()
        return event_row

    def complete_turn(
        self,
        turn: ChatTurn,
        *,
        status: TurnStatus,
        error: TurnError | None,
        completed_at: datetime,
        duration_ms: int | None,
        model: str | None = None,
        provider: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> ChatTurn:
        """Persist the final state and model metadata of one turn."""
        turn.status = _enum_value(status)
        turn.error = error.model_dump(
            mode="json") if error is not None else None
        turn.completed_at = completed_at
        turn.duration_ms = duration_ms
        turn.model = model
        turn.provider = provider
        turn.usage = usage
        self._session.flush()
        return turn

    def list_history_messages(self, row: ChatSession) -> list[dict[str, Any]]:
        """Project completed turn user/assistant items into model-history messages."""
        result = self._session.execute(
            select(ChatSessionItem)
            .join(ChatTurn, ChatSessionItem.turn_id == ChatTurn.id)
            .where(
                ChatSessionItem.session_id == row.id,
                ChatTurn.status == TurnStatus.COMPLETED.value,
                ChatSessionItem.item_type.in_(_SEARCHABLE_ITEM_TYPES),
            )
            .order_by(ChatTurn.id.asc(), ChatSessionItem.sequence.asc())
        )
        messages: list[dict[str, Any]] = []
        for item in result.scalars().all():
            message = _history_message_from_payload(item.payload)
            if message is not None:
                messages.append(message)
        return messages

    def list_session_timeline(self, row: ChatSession) -> list[dict[str, Any]]:
        """Return canonical turns with ordered session item payloads."""
        turns_result = self._session.execute(
            select(ChatTurn)
            .where(ChatTurn.session_id == row.id)
            .order_by(ChatTurn.id.asc())
        )
        turns = list(turns_result.scalars().all())
        if not turns:
            return []
        turn_ids = tuple(turn.id for turn in turns)
        items_result = self._session.execute(
            select(ChatSessionItem)
            .where(ChatSessionItem.turn_id.in_(turn_ids))
            .order_by(ChatSessionItem.turn_id.asc(), ChatSessionItem.sequence.asc())
        )
        items_by_turn: dict[int, list[ChatSessionItem]] = {}
        for item in items_result.scalars().all():
            items_by_turn.setdefault(item.turn_id, []).append(item)
        return [
            {
                "turn_id": turn.public_id,
                "status": turn.status,
                "model": turn.model,
                "provider": turn.provider,
                "usage": turn.usage,
                "error": turn.error,
                "started_at": _datetime_to_iso(turn.started_at),
                "completed_at": _datetime_to_iso(turn.completed_at),
                "duration_ms": turn.duration_ms,
                "items": [
                    dict(item.payload)
                    for item in items_by_turn.get(turn.id, [])
                ],
            }
            for turn in turns
        ]

    def list_sessions_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[ChatSession, int]], int]:
        """Return paginated active sessions and turn counts for one user."""
        filters = (
            ChatSession.user_id == user_id,
            ChatSession.deleted_at.is_(None),
        )
        total_result = self._session.execute(
            select(func.count()).select_from(ChatSession).where(*filters)
        )
        total = int(total_result.scalar_one() or 0)
        turn_count = func.count(ChatTurn.id).label("turn_count")
        rows_result = self._session.execute(
            select(ChatSession, turn_count)
            .outerjoin(ChatTurn, ChatTurn.session_id == ChatSession.id)
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
        """Search owned sessions by title and canonical item payloads."""
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

    def _next_turn_item_sequence(self, turn_id: int) -> int:
        """Return the next item sequence number for one turn."""
        result = self._session.execute(
            select(func.max(ChatSessionItem.sequence)).where(
                ChatSessionItem.turn_id == turn_id
            )
        )
        current = result.scalar_one_or_none()
        return int(current or 0) + 1

    def _next_turn_event_sequence(self, turn_id: int) -> int:
        """Return the next event sequence number for one turn."""
        result = self._session.execute(
            select(func.max(ChatSessionEvent.sequence)).where(
                ChatSessionEvent.turn_id == turn_id
            )
        )
        current = result.scalar_one_or_none()
        return int(current or 0) + 1


def _enum_value(value) -> str:
    """Return a persisted string for enum-like values."""
    return str(getattr(value, "value", value))


def _item_started_at(item):
    """Return the best started timestamp from an item payload."""
    return getattr(item, "started_at", None) or getattr(item, "created_at", None)


def _item_completed_at(item):
    """Return the best completed timestamp from an item payload."""
    return getattr(item, "completed_at", None)


def _datetime_to_iso(value: datetime | None) -> str | None:
    """Return a JSON-friendly timestamp string for timeline responses."""
    if value is None:
        return None
    return value.isoformat()


def _history_message_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Project one user or assistant item payload into a role/content message."""
    item_type = str(payload.get("type") or "")
    if item_type == "user_message":
        content = _user_message_text(payload)
        role = ChatCompletionRole.USER.value
    elif item_type == "agent_message":
        content = str(payload.get("text") or "")
        role = ChatCompletionRole.ASSISTANT.value
    else:
        return None
    if not content:
        return None
    return {
        "role": role,
        "content": content,
        "metadata": dict(payload.get("metadata") or {}),
    }


def _user_message_text(payload: dict[str, Any]) -> str:
    """Return joined text blocks from a persisted UserMessageItem payload."""
    blocks = payload.get("content") or []
    if not isinstance(blocks, list):
        return ""
    texts = [
        str(block.get("text") or "")
        for block in blocks
        if isinstance(block, dict) and block.get("text")
    ]
    return "\n".join(texts)
