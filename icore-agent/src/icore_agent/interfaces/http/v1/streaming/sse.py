"""Server-Sent Events adapter for HTTP v1 streaming responses."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from icore_agent.domain.agent.turn import TurnEvent, TurnEventKind

SSE_HEARTBEAT_SEC = 15


def encode_sse_event(event: TurnEvent) -> str:
    """Encode one application stream event as an SSE data frame."""
    payload = event.to_payload()
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def sse_frames(
    events: AsyncIterator[TurnEvent],
    *,
    heartbeat_sec: int = SSE_HEARTBEAT_SEC,
) -> AsyncIterator[str]:
    """Convert application events into SSE frames with transport heartbeats."""
    iterator = events.__aiter__()
    pending: asyncio.Task[TurnEvent] | None = asyncio.create_task(
        iterator.__anext__()
    )
    try:
        while pending is not None:
            done, _ = await asyncio.wait({pending}, timeout=heartbeat_sec)
            if not done:
                yield ": keep-alive\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            yield encode_sse_event(event)
            if event.kind in {
                TurnEventKind.TURN_COMPLETED,
                TurnEventKind.TURN_FAILED,
                TurnEventKind.TURN_ABORTED,
            }:
                break
            pending = asyncio.create_task(iterator.__anext__())
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
    yield "data: [DONE]\n\n"


def sse_response(
    events: AsyncIterator[TurnEvent],
    *,
    session_id: str,
) -> StreamingResponse:
    """Build a FastAPI streaming response for chat SSE events."""
    return StreamingResponse(
        sse_frames(events),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
