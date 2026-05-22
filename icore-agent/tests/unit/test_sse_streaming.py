"""Tests for HTTP v1 SSE streaming adapter."""

from __future__ import annotations

import pytest

from icore_agent.application.chat import ChatStreamEvent, ChatStreamEventKind
from icore_agent.interfaces.http.v1.streaming import encode_sse_event, sse_frames


def test_encode_sse_event_serializes_json_data_frame() -> None:
    """Typed chat events should be encoded as JSON SSE data frames."""
    event = ChatStreamEvent.token("你")
    frame = encode_sse_event(event)

    assert event.kind is ChatStreamEventKind.TOKEN
    assert frame == 'data: {"type": "token", "text": "你"}\n\n'


@pytest.mark.asyncio
async def test_sse_frames_appends_done_sentinel() -> None:
    """SSE adapter should keep the existing [DONE] sentinel."""
    frames = [frame async for frame in sse_frames(_events())]

    assert frames == [
        'data: {"type": "status", "step": 1, "tool": "chat", "input_preview": "启动 chat"}\n\n',
        'data: {"type": "done"}\n\n',
        "data: [DONE]\n\n",
    ]


async def _events():
    """Yield a small deterministic event stream."""
    yield ChatStreamEvent.status(step=1, tool="chat", input_preview="启动 chat")
    yield ChatStreamEvent.done()
