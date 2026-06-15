"""Tests for HTTP v1 SSE streaming adapter."""

from __future__ import annotations

import pytest

from icore_agent.domain.agent.session import AgentMessageItem
from icore_agent.domain.agent.turn import Turn, TurnEvent, TurnEventKind
from icore_agent.interfaces.http.v1.streaming import encode_sse_event, sse_frames


def test_encode_sse_event_serializes_json_data_frame() -> None:
    """Typed turn events should be encoded as JSON SSE data frames."""
    event = TurnEvent.item_delta(
        session_id="session-1",
        turn_id="turn-1",
        item_id="item-1",
        delta={"text": "你"},
    )
    frame = encode_sse_event(event)

    assert event.kind is TurnEventKind.ITEM_DELTA
    assert frame == (
        'data: {"type": "item_delta", "session_id": "session-1", '
        '"turn_id": "turn-1", "item_id": "item-1", '
        '"delta": {"text": "你"}}\n\n'
    )


def test_turn_completed_payload_omits_internal_turn_state() -> None:
    """SSE payloads should not expose the internal Turn aggregate."""
    turn = Turn(session_id="session-1", id="turn-1")
    event = TurnEvent.turn_completed(
        session_id="session-1",
        turn_id="turn-1",
        reply="ok",
        turn=turn,
    )

    assert event.turn is turn
    assert event.to_payload() == {
        "type": "turn_completed",
        "session_id": "session-1",
        "turn_id": "turn-1",
        "reply": "ok",
    }


@pytest.mark.asyncio
async def test_sse_frames_appends_done_sentinel() -> None:
    """SSE adapter should keep the existing [DONE] sentinel."""
    frames = [frame async for frame in sse_frames(_events())]

    assert frames == [
        'data: {"type": "item_started", "session_id": "session-1", "turn_id": "turn-1", "item_id": "item-1", "item": {"id": "item-1", "status": "in_progress", "created_at": "2026-06-08T00:00:00Z", "completed_at": null, "type": "agent_message", "text": ""}}\n\n',
        'data: {"type": "turn_completed", "session_id": "session-1", "turn_id": "turn-1", "reply": "ok"}\n\n',
        "data: [DONE]\n\n",
    ]


async def _events():
    """Yield a small deterministic event stream."""
    yield TurnEvent.item_started(
        session_id="session-1",
        turn_id="turn-1",
        item=AgentMessageItem(
            id="item-1",
            created_at="2026-06-08T00:00:00Z",
        ),
    )
    yield TurnEvent.turn_completed(
        session_id="session-1",
        turn_id="turn-1",
        reply="ok",
    )
