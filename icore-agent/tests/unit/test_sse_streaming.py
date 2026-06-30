"""Tests for HTTP v1 SSE streaming adapter."""

from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import UTC, datetime

import pytest

from icore_agent.domain.agent.session import AgentMessageItem
from icore_agent.domain.agent.turn import Turn, TurnError, TurnEvent, TurnEventKind
from icore_agent.interfaces.http.v1.streaming import encode_sse_event, sse_frames


def test_encode_sse_event_serializes_json_data_frame() -> None:
    """Typed turn events should be encoded as JSON SSE data frames."""
    event = TurnEvent(
        kind=TurnEventKind.ITEM_DELTA,
        session_id="session-1",
        turn_id="turn-1",
        item_id="item-1",
        delta={"text_append": "你"},
        event_id="event-1",
        seq=7,
        schema_version=1,
        created_at=datetime(2026, 6, 8, 0, 0, 0, tzinfo=UTC),
        run_id="run-1",
    )
    frame = encode_sse_event(event)

    assert event.kind is TurnEventKind.ITEM_DELTA
    assert frame == (
        'data: {"type": "item_delta", "session_id": "session-1", '
        '"turn_id": "turn-1", "event_id": "event-1", "seq": 7, '
        '"schema_version": 1, "created_at": "2026-06-08T00:00:00Z", '
        '"run_id": "run-1", "item_id": "item-1", '
        '"delta": {"text_append": "你"}}\n\n'
    )


def test_turn_completed_payload_includes_final_turn_snapshot() -> None:
    """Terminal events should expose the canonical final turn snapshot."""
    turn = Turn(session_id="session-1", id="turn-1")
    turn.upsert_item(AgentMessageItem(id="assistant-1", text="ok"))
    event = TurnEvent.turn_completed(
        session_id="session-1",
        turn_id="turn-1",
        reply="ok",
        turn=turn,
    )

    assert event.turn is turn
    payload = event.to_payload()
    assert payload["type"] == "turn_completed"
    assert payload["reply"] == "ok"
    assert payload["turn"]["turn_id"] == "turn-1"
    assert payload["turn"]["items"][0]["id"] == "assistant-1"
    assert payload["turn"]["items"][0]["text"] == "ok"


def test_turn_failed_payload_includes_error_and_final_turn_snapshot() -> None:
    """Failed terminal events should include both error and final turn."""
    turn = Turn(session_id="session-1", id="turn-1")
    error = TurnError(message="model unavailable", code="RuntimeError")
    event = TurnEvent.turn_failed(
        session_id="session-1",
        turn_id="turn-1",
        error=error,
        reply="partial",
        turn=turn,
    )

    assert event.turn is turn
    payload = event.to_payload()
    assert payload["type"] == "turn_failed"
    assert payload["error"] == {
        "message": "model unavailable",
        "code": "RuntimeError",
        "details": None,
    }
    assert payload["turn"]["turn_id"] == "turn-1"


@pytest.mark.asyncio
async def test_sse_frames_appends_done_sentinel() -> None:
    """SSE adapter should keep the existing [DONE] sentinel."""
    frames = [frame async for frame in sse_frames(_events())]

    payloads = [_payload(frame) for frame in frames[:-1]]
    assert [payload["type"] for payload in payloads] == [
        "item_started",
        "turn_completed",
    ]
    assert payloads[-1]["turn"]["turn_id"] == "turn-1"
    assert frames[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_sse_frames_stops_on_aborted_turn() -> None:
    """SSE adapter should close the stream when a turn is aborted."""
    frames = [frame async for frame in sse_frames(_aborted_events())]

    payload = _payload(frames[0])
    assert payload["type"] == "turn_aborted"
    assert payload["turn"]["turn_id"] == "turn-1"
    assert frames[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_sse_frames_converts_started_stream_exception_to_turn_failed() -> None:
    """After turn_started, upstream failures should terminate inside the stream."""
    frames = [frame async for frame in sse_frames(_started_then_failing_events())]

    payloads = [_payload(frame) for frame in frames[:-1]]
    assert [payload["type"] for payload in payloads] == [
        "turn_started",
        "turn_failed",
    ]
    assert payloads[1]["session_id"] == "session-1"
    assert payloads[1]["turn_id"] == "turn-1"
    assert payloads[1]["error"]["message"] == "boom"
    assert frames[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_sse_frames_consumes_event_source_in_one_context() -> None:
    """SSE iteration should not reset ContextVar tokens across tasks."""
    usage_events = ContextVar("turn_usage_events", default=None)

    async def _context_events():
        token = usage_events.set([])
        try:
            yield TurnEvent.item_delta(
                session_id="session-1",
                turn_id="turn-1",
                item_id="item-1",
                delta={"text_append": "ok"},
            )
        finally:
            usage_events.reset(token)

    frames = [frame async for frame in sse_frames(_context_events())]

    assert _payload(frames[0])["delta"] == {"text_append": "ok"}
    assert frames[-1] == "data: [DONE]\n\n"


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
        turn=Turn(session_id="session-1", id="turn-1"),
    )


async def _aborted_events():
    """Yield a minimal aborted terminal stream."""
    yield TurnEvent.turn_aborted(
        session_id="session-1",
        turn_id="turn-1",
        reply="partial",
        turn=Turn(session_id="session-1", id="turn-1"),
    )


async def _started_then_failing_events():
    """Yield a started turn and then raise to exercise terminal conversion."""
    yield TurnEvent.turn_started(
        session_id="session-1",
        turn_id="turn-1",
    )
    raise RuntimeError("boom")


def _payload(frame: str) -> dict:
    """Decode a JSON SSE data frame."""
    assert frame.startswith("data: ")
    return json.loads(frame.removeprefix("data: ").strip())
