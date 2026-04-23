"""Agent API endpoints.

POST /api/v1/agent/chat         — single-turn or multi-turn (streaming SSE)
POST /api/v1/agent/sequential   — run a mini-SWE-agent sequential task
DELETE /api/v1/agent/session/{id} — clear conversation memory
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import uuid
import structlog
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from typing import Annotated

from fastapi import File, Form, UploadFile

from ...config import settings
from ...engine.orchestrator import create_orchestrator
from ...engine.sequential import SequentialAgent
from ...memory.conversation import memory
from ...memory.attachment_store import attachments
from ...api.routers.knowledge import _parse_file, SUPPORTED_EXTENSIONS

log = structlog.get_logger()
router = APIRouter()

# ── Intent classifier ─────────────────────────────────────────────────────
# Purely rule-based: zero latency, zero cost.
# Returns True when the message is conversational-only (no tools needed).

_CHAT_PATTERNS = re.compile(
    r"^("
    # Chinese greetings & fillers
    r"你好|您好|嗨|hi|hello|hey|哈喽"
    r"|早上好|下午好|晚上好|早安|晚安"
    r"|谢谢|谢谢你|谢谢您|感谢|多谢|thx|thanks|thank you"
    r"|好的|好|明白|收到|了解|知道了|好的好的|嗯|哦|哈哈|哈"
    r"|再见|拜拜|byebye|bye|886|88"
    r"|你是谁|你叫什么|你叫什么名字|你是什么|介绍一下你自己|自我介绍"
    r"|你能做什么|你有什么功能|你的功能是什么|你会什么"
    r"|没问题|没事|可以|行|好啊|没关系|不用了|不用谢"
    # English greetings
    r"|good morning|good afternoon|good evening|good night"
    r"|who are you|what are you|what can you do|tell me about yourself"
    r"|ok|okay|got it|sure|alright|no problem|never mind"
    r")$",
    re.IGNORECASE,
)

_TASK_KEYWORDS = re.compile(
    # 中文：明确的动作指令，要求搜索/查/找/分析某内容、操作文件等
    r"搜索|查询|查找|查一下|帮我搜|帮我找|帮我查|帮我分析|帮我写|帮我生成"
    r"|总结.*文|翻译.*成|生成.*代码|写.*代码|写.*程序|写.*脚本|编写"
    r"|文档|知识库|政策|规定|合同|手册|上传|下载"
    # 英文：明确的动作指令，避免 find/write/search 在建议句中误触发
    r"|look up|web search|fetch|scrape"
    r"|summarize.*(document|file|text|report|article|page|content)"
    r"|summarise.*(document|file|text|report|article|page|content)"
    r"|translate.*(into|to) [a-z]"
    r"|write.*code|generate.*code|write.*script|write.*program"
    r"|analyze.*data|analyse.*data"
    r"|document|policy|contract|manual|upload",
    re.IGNORECASE,
)

# 建议/看法/解释类问题：LLM 自己就能回答，不需要调工具
_CHAT_LIKE_PATTERNS = re.compile(
    r"should|could|would you|what.*think|what.*opinion|what.*focus"
    r"|how.*improve|how.*better|tell me about|explain|describe|what is|what are"
    r"|why.*is|why.*do|why.*should|how does|how do"
    r"|你觉得|你认为|怎么看|有什么建议|怎么理解|解释一下|介绍.*一下|什么是|为什么",
    re.IGNORECASE,
)


def _classify_intent(message: str) -> str:
    """Classify a user message as 'chat' or 'task'.

    'chat'  → Orchestrator runs without sub-agent tools (direct LLM reply).
    'task'  → Orchestrator runs with all sub-agent tools attached.

    Rules (in priority order):
      1. If the stripped text matches a known conversational pattern → chat
      2. If the text contains task-oriented keywords            → task
      3. If the text is very short (≤ 6 chars) and no task kw  → chat
      4. Default                                                → task
    """
    stripped = message.strip()
    # 1. 纯聊天模式（问候、感谢、再见等）
    if _CHAT_PATTERNS.fullmatch(stripped):
        return "chat"
    # 2. 明确的任务关键词（搜索/查/文件操作等）
    if _TASK_KEYWORDS.search(stripped):
        return "task"
    # 3. 短消息（简单确认/回应）
    if len(stripped) <= 6:
        return "chat"
    # 4. 建议/看法/解释类问题 —— LLM 自己就能答，不需要工具
    if _CHAT_LIKE_PATTERNS.search(stripped):
        return "chat"
    # 5. 默认为 chat：大部分问题 LLM 知识储备足够，工具应按需触发而非总是开启
    return "chat"


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


# ── Shared helpers ────────────────────────────────────────────────────────

def _to_strands_messages(history: list[dict]) -> list[dict]:
    """Convert Redis message dicts to Strands Message format.

    Redis format:  {"role": "user",      "content": "text"}
    Strands format:{"role": "user",      "content": [{"type": "text", "text": "..."}]}
    """
    return [
        {"role": m["role"], "content": [{"type": "text", "text": m["content"]}]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


async def _load_context(
    session_id: str,
) -> tuple[str | None, list[dict], str | None, bool]:
    """Fetch Redis history, inline attachments concurrently.

    Returns:
        (summary, strands_history, inline_text, has_rag)
    """
    (summary, history), inline_text, has_rag = await asyncio.gather(
        memory.get_context(session_id),
        attachments.get_inline_text(session_id),
        attachments.has_rag_docs(session_id),
    )
    return (
        summary or None,
        _to_strands_messages(history),
        inline_text or None,
        has_rag,
    )


# ── Chat endpoint (SSE streaming) ─────────────────────────────────────────

async def _stream_agent(message: str, session_id: str) -> AsyncGenerator[str, None]:
    """真正的 token 级 SSE 流：Strands callback_handler → asyncio.Queue → SSE。"""
    loop = asyncio.get_event_loop()
    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    # ── 0. 意图分类（零延迟规则分类器）──────────────────────────────────
    intent = _classify_intent(message)
    enable_tools = intent == "task"
    log.info("intent_classified", intent=intent, enable_tools=enable_tools,
             session_id=session_id, msg_preview=message[:60])

    # ── 1. 加载短期上下文 + 附件 ─────────────────────────────────────────
    summary, strands_history, inline_text, has_rag = await _load_context(session_id)
    # 有 RAG 文档时强制开启工具（knowledge_agent 需要检索）
    if has_rag:
        enable_tools = True

    full_reply: list[str] = []

    def on_stream_event(**kwargs):
        """Strands 在 worker 线程中同步调用此回调，桥接到 asyncio Queue。"""
        # ── 工具调用可观测性 ──────────────────────────────────────────────
        event_loop = kwargs.get("event_loop_metrics")
        current_tool = kwargs.get("current_tool_use")
        if current_tool:
            tool_name = current_tool.get("name", "unknown")
            tool_input = current_tool.get("input", {})
            log.info(
                "tool_call",
                tool=tool_name,
                input_preview=str(tool_input)[:120],
                session_id=session_id,
            )
        # ── 流式 token ──────────────────────────────────────────────────
        token = kwargs.get("data")
        if token and isinstance(token, str):
            asyncio.run_coroutine_threadsafe(q.put(("token", token)), loop)

    def run_agent():
        try:
            orchestrator = create_orchestrator(
                callback_handler=on_stream_event,
                summary=summary,
                attachments_text=inline_text,
                enable_tools=enable_tools,
            )
            # Pre-populate with recent history as proper role-tagged messages
            orchestrator.messages = strands_history
            orchestrator(message)
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

    # ── 2. 保存短期记忆（Redis）────────────────────────────────────────────
    reply_text = "".join(full_reply)
    await memory.append_message(session_id, "user", message)
    await memory.append_message(session_id, "assistant", reply_text)



@router.post("/chat", summary="Chat with the agent (SSE streaming)")
async def chat(req: ChatRequest):
    intent = _classify_intent(req.message)
    enable_tools = intent == "task"
    log.info(
        "chat_request",
        session_id=req.session_id,
        stream=req.stream,
        intent=intent,
        enable_tools=enable_tools,
    )

    if req.stream:
        return StreamingResponse(
            _stream_agent(req.message, req.session_id),
            media_type="text/event-stream",
            headers={"X-Session-Id": req.session_id},
        )

    # Non-streaming fallback
    summary, strands_history, inline_text, has_rag = await _load_context(req.session_id)
    if has_rag:
        enable_tools = True
    orchestrator = create_orchestrator(
        summary=summary,
        attachments_text=inline_text,
        enable_tools=enable_tools,
    )
    orchestrator.messages = strands_history
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


# ── Attachment management ─────────────────────────────────────────────────

class AttachmentInfo(BaseModel):
    filename: str
    char_count: int
    mode: str   # "inline" | "rag"
    uploaded_at: float


class AttachResponse(BaseModel):
    filename: str
    char_count: int
    mode: str


@router.post("/attach", response_model=AttachResponse,
             summary="Upload a document and attach it to the session context")
async def attach_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT, or MD file")],
    session_id: Annotated[str, Form(description="Session ID to attach the document to")],
) -> AttachResponse:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415,
                            detail=f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}")
    data = await file.read()
    if len(data) > settings.file_ops_max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413,
                            detail=f"File exceeds {settings.file_ops_max_size_mb} MB limit")
    try:
        text = _parse_file(file.filename or "upload", data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}") from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="File appears to be empty or unreadable")

    att = await attachments.add(session_id, file.filename or "upload", text)
    log.info("attachment_added", session_id=session_id,
             filename=att["filename"], mode=att["mode"], chars=att["char_count"])
    return AttachResponse(filename=att["filename"], char_count=att["char_count"], mode=att["mode"])


@router.get("/attachments/{session_id}", response_model=list[AttachmentInfo],
            summary="List documents attached to a session")
async def list_attachments(session_id: str) -> list[AttachmentInfo]:
    info = await attachments.list_info(session_id)
    return [AttachmentInfo(**a) for a in info]


@router.delete("/attachments/{session_id}/{filename}",
               summary="Remove a document from session context")
async def remove_attachment(session_id: str, filename: str) -> dict:
    removed = await attachments.remove(session_id, filename)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Attachment '{filename}' not found")
    return {"removed": True, "filename": filename, "session_id": session_id}


# ── Session management ────────────────────────────────────────────────────

@router.delete("/session/{session_id}", summary="Clear conversation memory for a session")
async def clear_session(session_id: str) -> dict:
    await asyncio.gather(memory.clear(session_id), attachments.clear(session_id))
    return {"cleared": True, "session_id": session_id}
