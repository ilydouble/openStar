"""Server-Sent Events adapter for HTTP v1 streaming responses."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress

from fastapi.responses import StreamingResponse

from icore_agent.domain.agent.turn import TurnEvent, TurnEventKind

SSE_HEARTBEAT_SEC = 15
_TERMINAL_EVENTS = {
    TurnEventKind.TURN_COMPLETED,
    TurnEventKind.TURN_FAILED,
    TurnEventKind.TURN_ABORTED,
}


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
    sentinel = object()
    queue: asyncio.Queue[TurnEvent | Exception | object] = asyncio.Queue(
        maxsize=1)

    async def _produce_events() -> None:
        """Consume the application stream in one task to preserve ContextVars."""
        try:
            async for event in events:
                await queue.put(event)
                if event.kind in _TERMINAL_EVENTS:
                    break
        except Exception as exc:
            await queue.put(exc)
        finally:
            await queue.put(sentinel)

    producer = asyncio.create_task(_produce_events())
    try:
        while True:
            try:
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=heartbeat_sec,
                )
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if item is sentinel:
                break
            if isinstance(item, Exception):
                raise item
            event = item
            yield encode_sse_event(event)
            if event.kind in _TERMINAL_EVENTS:
                break
    finally:
        if not producer.done():
            producer.cancel()
        with suppress(asyncio.CancelledError):
            await producer
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
