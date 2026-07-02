"""One-time data migration: rebuild turns/session_items from the legacy
``messages`` table so pre-refactor chat history shows up in the new
turn-based timeline again.

Idempotent — skips any session that already has at least one row in
``turns`` (covers sessions created under the new architecture). Reads only
from ``messages``; writes only to ``turns``/``session_items``. The legacy
``messages`` table is left untouched.

Run inside the icore-agent container:
    docker exec icore-agent python scripts/backfill_turns_from_messages.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import groupby

from sqlalchemy import text

from icore_agent.domain.agent.session.session_items import (
    AgentMessageItem,
    SessionItemStatus,
    ToolCallItem,
    ToolCallStatus,
    ToolCallResult,
    ToolCallError,
    ToolFunction,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.infrastructure.persistence.sessions.models import (
    ChatSessionItem,
    ChatTurn,
)
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import (
    sync_session_scope,
)


def _to_dt(epoch_seconds: int) -> datetime:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)


def _tool_payload(content: str, metadata: dict) -> tuple[str, str | None]:
    """Extract a display text and error flag from a legacy tool message."""
    text_out = content
    is_error = False
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return text_out, None
    if isinstance(parsed, dict):
        blocks = parsed.get("content") or []
        if blocks and isinstance(blocks, list) and isinstance(blocks[0], dict):
            text_out = blocks[0].get("text", content)
        is_error = parsed.get("status") == "error"
    return text_out, ("error" if is_error else None)


def main() -> None:
    created_turns = 0
    created_items = 0
    skipped_sessions = 0

    with sync_session_scope() as session:
        existing = session.execute(
            text("SELECT DISTINCT session_id FROM turns")
        ).scalars().all()
        sessions_with_turns = set(existing)

        rows = session.execute(
            text(
                "SELECT session_id, role, content, sequence, created_at, "
                "metadata FROM messages ORDER BY session_id, sequence"
            )
        ).mappings().all()

        for session_id, msgs in groupby(rows, key=lambda r: r["session_id"]):
            if session_id in sessions_with_turns:
                skipped_sessions += 1
                continue
            msgs = list(msgs)

            # New turn starts at each user message; assistant/tool rows
            # immediately following attach to that turn.
            groups: list[list] = []
            for m in msgs:
                if m["role"] == "user" or not groups:
                    groups.append([m])
                else:
                    groups[-1].append(m)

            for group in groups:
                started = _to_dt(group[0]["created_at"])
                completed = _to_dt(group[-1]["created_at"])
                duration_ms = max(
                    int((completed - started).total_seconds() * 1000), 0)

                turn = ChatTurn(
                    session_id=session_id,
                    public_id=None,
                    status="completed",
                    error=None,
                    started_at=started,
                    completed_at=completed,
                    duration_ms=duration_ms,
                    model=None,
                    provider=None,
                    usage=None,
                )
                from icore_agent.domain.identifiers import uuid7
                turn.public_id = str(uuid7())
                session.add(turn)
                session.flush()
                created_turns += 1

                for seq, m in enumerate(group, start=1):
                    role = m["role"]
                    ts = _to_dt(m["created_at"])
                    item = None

                    if role == "user":
                        item = UserMessageItem(
                            status=SessionItemStatus.COMPLETED,
                            created_at=ts,
                            completed_at=ts,
                            content=[UserInput(
                                type=UserInputType.TEXT, text=m["content"])],
                        )
                    elif role == "assistant":
                        item = AgentMessageItem(
                            status=SessionItemStatus.COMPLETED,
                            created_at=ts,
                            completed_at=ts,
                            text=m["content"],
                        )
                    elif role == "tool":
                        meta = m["metadata"] or {}
                        tool_name = meta.get("tool_name") or "unknown_tool"
                        text_out, error_flag = _tool_payload(
                            m["content"], meta)
                        item = ToolCallItem(
                            status=(
                                ToolCallStatus.FAILED if error_flag
                                else ToolCallStatus.COMPLETED
                            ),
                            created_at=ts,
                            completed_at=ts,
                            provider_tool_call_id=meta.get("tool_call_id"),
                            function=ToolFunction(name=tool_name),
                            result=(
                                None if error_flag
                                else ToolCallResult(content=text_out)
                            ),
                            error=(
                                ToolCallError(message=text_out)
                                if error_flag else None
                            ),
                            started_at=ts,
                        )
                    else:
                        continue

                    payload = item.model_dump(mode="json")
                    session.add(ChatSessionItem(
                        session_id=session_id,
                        turn_id=turn.id,
                        public_id=payload["id"],
                        item_type=str(payload["type"]),
                        status=str(payload["status"]),
                        sequence=seq,
                        payload=payload,
                        started_at=ts,
                        completed_at=ts,
                    ))
                    created_items += 1

        session.commit()

    print(
        f"Backfill complete: {created_turns} turns, {created_items} items "
        f"created; {skipped_sessions} sessions already had turns (skipped)."
    )


if __name__ == "__main__":
    main()
