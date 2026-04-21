"""Agent API endpoints.

POST /api/v1/agent/chat         — single-turn or multi-turn (streaming SSE)
POST /api/v1/agent/sequential   — run a mini-SWE-agent sequential task
DELETE /api/v1/agent/session/{id} — clear conversation memory
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
import structlog
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...engine.orchestrator import create_orchestrator
from ...engine.sequential import SequentialAgent
from ...memory.conversation import memory

log = structlog.get_logger()
router = APIRouter()


# ── Request / Response schemas ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32_000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream: bool = True
    tenant_code: str = ""


class ChatResponse(BaseModel):
    session_id: str
    reply: str


class SequentialRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=8_000)
    use_docker: bool = False


class SequentialResponse(BaseModel):
    status: str
    output: str
    steps: int


# ── Chat endpoint (SSE streaming) ─────────────────────────────────────────

async def _stream_agent(message: str, session_id: str) -> AsyncGenerator[str, None]:
    """真正的 token 级 SSE 流：Strands callback_handler → asyncio.Queue → SSE。"""
    loop = asyncio.get_event_loop()
    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    history = await memory.get_messages(session_id)
    prompt = message
    if history:
        context = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-10:])
        prompt = f"Previous conversation:\n{context}\n\nUser: {message}"

    full_reply: list[str] = []

    def on_stream_event(**kwargs):
        """Strands 在 worker 线程中同步调用此回调，桥接到 asyncio Queue。"""
        token = kwargs.get("data")
        if token and isinstance(token, str):
            asyncio.run_coroutine_threadsafe(q.put(("token", token)), loop)

    def run_agent():
        try:
            orchestrator = create_orchestrator(callback_handler=on_stream_event)
            orchestrator(prompt)
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(q.put(("error", str(exc))), loop)
        finally:
            asyncio.run_coroutine_threadsafe(q.put(("done", "")), loop)

    threading.Thread(target=run_agent, daemon=True).start()

    try:
        while True:
            kind, data = await asyncio.wait_for(q.get(), timeout=120)
            if kind == "token":
                full_reply.append(data)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            elif kind == "error":
                log.error("agent_stream_error", error=data, session_id=session_id)
                yield f"data: {json.dumps('[ERROR] ' + data, ensure_ascii=False)}\n\n"
                break
            else:  # done
                break
    except asyncio.TimeoutError:
        yield f"data: {json.dumps('[ERROR] Agent 响应超时', ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
    reply_text = "".join(full_reply)
    await memory.append_message(session_id, "user", message)
    await memory.append_message(session_id, "assistant", reply_text)


@router.post("/chat", summary="Chat with the agent (SSE streaming)")
async def chat(req: ChatRequest):
    log.info("chat_request", session_id=req.session_id, stream=req.stream)

    if req.stream:
        return StreamingResponse(
            _stream_agent(req.message, req.session_id),
            media_type="text/event-stream",
            headers={"X-Session-Id": req.session_id},
        )

    # Non-streaming fallback
    orchestrator = create_orchestrator()
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, orchestrator, req.message)
        reply = str(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await memory.append_message(req.session_id, "user", req.message)
    await memory.append_message(req.session_id, "assistant", reply)
    return ChatResponse(session_id=req.session_id, reply=reply)


# ── Sequential task endpoint ──────────────────────────────────────────────

@router.post("/sequential", response_model=SequentialResponse,
             summary="Run a sequential bash task (mini-SWE-agent style)")
async def run_sequential(req: SequentialRequest) -> SequentialResponse:
    log.info("sequential_request", task_preview=req.task[:100])

    if req.use_docker:
        from ...engine.sequential.environment import DockerEnvironment
        env = DockerEnvironment()
    else:
        from ...engine.sequential.environment import LocalEnvironment
        env = LocalEnvironment()

    agent = SequentialAgent(environment=env)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, agent.run, req.task)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SequentialResponse(status=result.status, output=result.output, steps=result.steps)


# ── Session management ────────────────────────────────────────────────────

@router.delete("/session/{session_id}", summary="Clear conversation memory for a session")
async def clear_session(session_id: str) -> dict:
    await memory.clear(session_id)
    return {"cleared": True, "session_id": session_id}
