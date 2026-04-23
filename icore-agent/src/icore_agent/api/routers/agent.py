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
from pathlib import Path
import structlog
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from typing import Annotated

from fastapi import File, Form, UploadFile

from ...config import settings
from ...engine.orchestrator import VALID_AGENT_HINTS, create_orchestrator
from ...engine.callback_ctx import set_parent_callback, reset_parent_callback
from ...engine.sequential import SequentialAgent
from ...memory.conversation import memory
from ...memory.attachment_store import attachments
from ...tools.image_tools import _SUPPORTED_IMAGE_EXTS
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
    # UI shortcut button binding. One of: research | code | knowledge |
    # image | data | chat. Takes precedence over the rule-based intent
    # classifier when supplied; unknown values are ignored.
    agent_hint: str = ""


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
) -> tuple[str | None, list[dict], str | None, bool, list[dict], list[dict]]:
    """Fetch Redis history, inline attachments, image and data refs concurrently.

    Returns:
        (summary, strands_history, inline_text, has_rag, image_refs, data_refs)
    """
    (summary, history), inline_text, has_rag, image_refs, data_refs = await asyncio.gather(
        memory.get_context(session_id),
        attachments.get_inline_text(session_id),
        attachments.has_rag_docs(session_id),
        attachments.get_image_refs(session_id),
        attachments.get_data_refs(session_id),
    )
    return (
        summary or None,
        _to_strands_messages(history),
        inline_text or None,
        has_rag,
        image_refs or [],
        data_refs or [],
    )


def _resolve_routing(message: str, agent_hint: str) -> tuple[str, bool, str | None]:
    """Apply agent_hint over the rule-based classifier.

    Returns (intent, enable_tools, effective_hint). If hint is set and valid,
    it wins: "chat" disables tools, any other valid hint enables them.
    """
    hint = (agent_hint or "").strip().lower()
    if hint in VALID_AGENT_HINTS:
        if hint == "chat":
            return "chat", False, hint
        return "task", True, hint
    intent = _classify_intent(message)
    return intent, intent == "task", None


# ── Chat endpoint (SSE streaming) ─────────────────────────────────────────

# SSE 心跳间隔（秒）：队列静默达到该值时，推一条 keep-alive 注释，
# 防止浏览器 / 反向代理在长任务中断开连接。
_SSE_HEARTBEAT_SEC = 15
# 总墙钟预算（秒）：单轮 agent 最长可运行时间，覆盖深度调研等耗时任务。
_SSE_WALL_BUDGET_SEC = 600


def _sse(event: dict) -> str:
    """Serialize a typed event as an SSE data frame."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _stream_agent(
    message: str, session_id: str, agent_hint: str = ""
) -> AsyncGenerator[str, None]:
    """Token 级 SSE 流 + 工具步骤状态推送 + 心跳防超时。

    SSE 事件类型：
      {"type":"status","tool":...,"input_preview":...,"step":N}  — 工具开始执行
      {"type":"token","text":...}                                 — LLM 流式 token
      {"type":"error","message":...}                              — 失败
      {"type":"done"}                                             — 本轮结束
    另外每 _SSE_HEARTBEAT_SEC 秒在静默时插入一条 ": keep-alive" 注释帧。
    """
    loop = asyncio.get_event_loop()
    q: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    # ── 0. 路由决策（agent_hint 优先于规则分类器）─────────────────────────
    intent, enable_tools, effective_hint = _resolve_routing(message, agent_hint)
    log.info("intent_classified", intent=intent, enable_tools=enable_tools,
             agent_hint=effective_hint, session_id=session_id,
             msg_preview=message[:60])

    # ── 1. 加载短期上下文 + 附件 ─────────────────────────────────────────
    summary, strands_history, inline_text, has_rag, image_refs, data_refs = \
        await _load_context(session_id)
    if has_rag or image_refs or data_refs:
        enable_tools = True

    # 路由完成即推首条状态 —— 避免子 agent 长时间工作时前端完全无反馈。
    route_label_map = {
        "research": "research_agent",
        "knowledge": "knowledge_agent",
        "image": "image_agent",
        "data": "data_agent",
        "code": "code_agent",
        "chat": "chat",
    }
    init_label = route_label_map.get(effective_hint or intent, "orchestrator")
    init_summary_bits: list[str] = []
    if has_rag:
        init_summary_bits.append("RAG 知识库已载入")
    if image_refs:
        init_summary_bits.append(f"图片 {len(image_refs)} 张")
    if data_refs:
        init_summary_bits.append(f"数据 {len(data_refs)} 份")
    init_preview = "，".join(init_summary_bits) or f"启动 {init_label}"
    await q.put(("status", {"tool": init_label, "input_preview": init_preview}))

    full_reply: list[str] = []
    # Strands 在工具执行期间会反复触发 current_tool_use delta；用 toolUseId
    # 去重，保证每次工具调用只推送一次 status 事件。
    seen_tool_ids: set[str] = set()

    def on_stream_event(**kwargs):
        """Strands worker 线程同步回调 → asyncio Queue。"""
        current_tool = kwargs.get("current_tool_use")
        if current_tool:
            tool_id = str(current_tool.get("toolUseId") or "")
            if tool_id and tool_id not in seen_tool_ids:
                seen_tool_ids.add(tool_id)
                tool_name = current_tool.get("name", "unknown")
                tool_input = current_tool.get("input", {})
                log.info("tool_call", tool=tool_name,
                         input_preview=str(tool_input)[:120], session_id=session_id)
                asyncio.run_coroutine_threadsafe(
                    q.put(("status", {
                        "tool": tool_name,
                        "input_preview": str(tool_input)[:200],
                    })),
                    loop,
                )
        token = kwargs.get("data")
        if token and isinstance(token, str):
            asyncio.run_coroutine_threadsafe(q.put(("token", token)), loop)

    def run_agent():
        token = set_parent_callback(on_stream_event)
        try:
            orchestrator = create_orchestrator(
                callback_handler=on_stream_event,
                summary=summary,
                attachments_text=inline_text,
                image_attachments=image_refs,
                data_attachments=data_refs,
                enable_tools=enable_tools,
                agent_hint=effective_hint,
                session_id=session_id,
            )
            orchestrator.messages = strands_history
            orchestrator(message)
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(q.put(("error", str(exc))), loop)
        finally:
            reset_parent_callback(token)
            asyncio.run_coroutine_threadsafe(q.put(("done", "")), loop)

    threading.Thread(target=run_agent, daemon=True).start()

    # ── 2. 心跳驱动的事件循环 ────────────────────────────────────────────
    start = loop.time()
    step_idx = 0
    timed_out = False
    while True:
        if loop.time() - start > _SSE_WALL_BUDGET_SEC:
            timed_out = True
            break
        try:
            kind, payload = await asyncio.wait_for(
                q.get(), timeout=_SSE_HEARTBEAT_SEC
            )
        except asyncio.TimeoutError:
            # 静默期间推心跳注释帧（不消耗业务事件，仅用于保活）
            yield ": keep-alive\n\n"
            continue

        if kind == "token":
            text = payload if isinstance(payload, str) else str(payload)
            full_reply.append(text)
            yield _sse({"type": "token", "text": text})
        elif kind == "status":
            step_idx += 1
            evt = {"type": "status", "step": step_idx}
            if isinstance(payload, dict):
                evt.update(payload)
            yield _sse(evt)
        elif kind == "error":
            msg = payload if isinstance(payload, str) else str(payload)
            log.error("agent_stream_error", error=msg, session_id=session_id)
            yield _sse({"type": "error", "message": msg})
            break
        else:  # done
            break

    if timed_out:
        log.warning("agent_stream_wall_timeout",
                    session_id=session_id, budget_sec=_SSE_WALL_BUDGET_SEC)
        yield _sse({
            "type": "error",
            "message": f"Agent 运行超过 {_SSE_WALL_BUDGET_SEC}s 预算，已中止",
        })

    yield _sse({"type": "done"})
    yield "data: [DONE]\n\n"

    # ── 3. 保存短期记忆（Redis）────────────────────────────────────────────
    reply_text = "".join(full_reply)
    await memory.append_message(session_id, "user", message)
    await memory.append_message(session_id, "assistant", reply_text)



@router.post("/chat", summary="Chat with the agent (SSE streaming)")
async def chat(req: ChatRequest):
    intent, enable_tools, effective_hint = _resolve_routing(req.message, req.agent_hint)
    log.info(
        "chat_request",
        session_id=req.session_id,
        stream=req.stream,
        intent=intent,
        enable_tools=enable_tools,
        agent_hint=effective_hint,
    )

    if req.stream:
        return StreamingResponse(
            _stream_agent(req.message, req.session_id, req.agent_hint),
            media_type="text/event-stream",
            headers={
                "X-Session-Id": req.session_id,
                # SSE 必备三件套：禁用任何中间层缓冲 / 缓存 / 压缩。
                # X-Accel-Buffering 会被 nginx 识别，Vite 的 http-proxy 在
                # 看到它时也会放弃自作主张的积攒策略，保证每次 yield 立刻
                # 到达浏览器。
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # Non-streaming fallback
    summary, strands_history, inline_text, has_rag, image_refs, data_refs = \
        await _load_context(req.session_id)
    if has_rag or image_refs or data_refs:
        enable_tools = True
    orchestrator = create_orchestrator(
        summary=summary,
        attachments_text=inline_text,
        image_attachments=image_refs,
        data_attachments=data_refs,
        enable_tools=enable_tools,
        agent_hint=effective_hint,
        session_id=req.session_id,
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
    mode: str   # "inline" | "rag" | "image" | "data"
    uploaded_at: float
    char_count: int | None = None   # text attachments only
    ref: str | None = None          # image / data attachments
    size: int | None = None         # image / data attachments
    ext: str | None = None          # data attachments
    row_count: int | None = None    # data attachments
    columns: list[dict] | None = None   # data attachments: [{name, dtype}]
    preview_md: str | None = None   # data attachments: head(N) markdown
    preview_error: str | None = None  # data attachments: parse error, if any


class AttachResponse(BaseModel):
    filename: str
    char_count: int
    mode: str


class ImageAttachResponse(BaseModel):
    filename: str
    ref: str
    size: int
    mode: str = "image"


class DataAttachResponse(BaseModel):
    filename: str
    ref: str
    size: int
    ext: str
    row_count: int | None = None
    columns: list[dict] = []
    preview_md: str = ""
    preview_error: str = ""
    mode: str = "data"


_SUPPORTED_DATA_EXTS = {".csv", ".xlsx", ".xls"}


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


# ── Image upload / serve ──────────────────────────────────────────────────

@router.post("/attach/image", response_model=ImageAttachResponse,
             summary="Upload an image (jpg/png/webp) and attach it to the session")
async def attach_image(
    file: Annotated[UploadFile, File(description="JPG, PNG, WEBP, BMP or GIF image")],
    session_id: Annotated[str, Form(description="Session ID to attach the image to")],
) -> ImageAttachResponse:
    filename = file.filename or "image"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED_IMAGE_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type '{ext}'. Supported: {sorted(_SUPPORTED_IMAGE_EXTS)}",
        )
    data = await file.read()
    limit = settings.image_upload_max_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {settings.image_upload_max_mb} MB limit",
        )
    record = await attachments.add_image(session_id, filename, data)
    return ImageAttachResponse(
        filename=record["filename"], ref=record["ref"], size=record["size"]
    )


@router.get("/images/{session_id}/{filename}",
            summary="Serve a session-scoped image")
async def get_image(session_id: str, filename: str):
    # Prevent path traversal — filename must not contain separators.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = Path(settings.image_save_dir) / session_id / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


# ── Data file upload (CSV / Excel) ────────────────────────────────────────

@router.post("/attach/data", response_model=DataAttachResponse,
             summary="Upload a CSV / Excel file to the session workspace for pandas analysis")
async def attach_data(
    file: Annotated[UploadFile, File(description="CSV, XLSX or XLS file")],
    session_id: Annotated[str, Form(description="Session ID to attach the data file to")],
) -> DataAttachResponse:
    filename = file.filename or "data"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED_DATA_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported data type '{ext}'. Supported: {sorted(_SUPPORTED_DATA_EXTS)}",
        )
    data = await file.read()
    limit = settings.data_upload_max_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Data file exceeds {settings.data_upload_max_mb} MB limit",
        )
    record = await attachments.add_data(session_id, filename, data)
    return DataAttachResponse(
        filename=record["filename"],
        ref=record["ref"],
        size=record["size"],
        ext=record["ext"],
        row_count=record.get("row_count"),
        columns=record.get("columns") or [],
        preview_md=record.get("preview_md") or "",
        preview_error=record.get("preview_error") or "",
    )


# ── Session management ────────────────────────────────────────────────────

@router.delete("/session/{session_id}", summary="Clear conversation memory for a session")
async def clear_session(session_id: str) -> dict:
    await asyncio.gather(memory.clear(session_id), attachments.clear(session_id))
    return {"cleared": True, "session_id": session_id}
