"""Agent chat handlers and streaming helpers."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections.abc import AsyncGenerator
from typing import Any, Protocol, cast

from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse

from icore_agent.lib.logging.app_logger import get_logger

from ....application.account import AccountService
from ....control_plane import clear_runtime_user, set_runtime_user
from ....engine.callback_ctx import reset_parent_callback, set_parent_callback
from ....memory.attachment_store import attachments
from ....memory.conversation import memory
from ...dependencies import get_account_service, get_current_user
from ..schemas.chat import ChatRequest, ChatResponse

log = get_logger(__name__)

VALID_AGENT_HINTS = {"research", "code", "knowledge", "image", "data", "chat"}

_CHAT_PATTERNS = re.compile(
    r"^("
    r"你好|您好|嗨|hi|hello|hey|哈喽"
    r"|早上好|下午好|晚上好|早安|晚安"
    r"|谢谢|谢谢你|谢谢您|感谢|多谢|thx|thanks|thank you"
    r"|好的|好|明白|收到|了解|知道了|好的好的|嗯|哦|哈哈|哈"
    r"|再见|拜拜|byebye|bye|886|88"
    r"|你是谁|你叫什么|你叫什么名字|你是什么|介绍一下你自己|自我介绍"
    r"|你能做什么|你有什么功能|你的功能是什么|你会什么"
    r"|没问题|没事|可以|行|好啊|没关系|不用了|不用谢"
    r"|good morning|good afternoon|good evening|good night"
    r"|who are you|what are you|what can you do|tell me about yourself"
    r"|ok|okay|got it|sure|alright|no problem|never mind"
    r")$",
    re.IGNORECASE,
)

_TASK_KEYWORDS = re.compile(
    r"搜索|查询|查找|查一下|帮我搜|帮我找|帮我查|帮我分析|帮我写|帮我生成"
    r"|总结.*文|翻译.*成|生成.*代码|写.*代码|写.*程序|写.*脚本|编写"
    r"|文档|知识库|政策|规定|合同|手册|上传|下载"
    r"|look up|web search|fetch|scrape"
    r"|summarize.*(document|file|text|report|article|page|content)"
    r"|summarise.*(document|file|text|report|article|page|content)"
    r"|translate.*(into|to) [a-z]"
    r"|write.*code|generate.*code|write.*script|write.*program"
    r"|analyze.*data|analyse.*data"
    r"|document|policy|contract|manual|upload",
    re.IGNORECASE,
)

_CHAT_LIKE_PATTERNS = re.compile(
    r"should|could|would you|what.*think|what.*opinion|what.*focus"
    r"|how.*improve|how.*better|tell me about|explain|describe|what is|what are"
    r"|why.*is|why.*do|why.*should|how does|how do"
    r"|你觉得|你认为|怎么看|有什么建议|怎么理解|解释一下|介绍.*一下|什么是|为什么",
    re.IGNORECASE,
)

_SSE_HEARTBEAT_SEC = 15
_SSE_WALL_BUDGET_SEC = 600


class AgentRunner(Protocol):
    """Minimal orchestrator surface used by the chat endpoint."""

    messages: list[dict[str, Any]]

    def __call__(self, message: str) -> Any:
        """Run one user message through the orchestrator."""
        ...


def create_orchestrator(*args: Any, **kwargs: Any) -> AgentRunner:
    """Build an orchestrator and expose the runtime methods this module needs."""
    from ....engine.orchestrator import create_orchestrator as _create_orchestrator

    return cast(AgentRunner, _create_orchestrator(*args, **kwargs))


def _classify_intent(message: str) -> str:
    """Classify a user message as chat or task."""
    stripped = message.strip()
    if _CHAT_PATTERNS.fullmatch(stripped):
        return "chat"
    if _TASK_KEYWORDS.search(stripped):
        return "task"
    if len(stripped) <= 6:
        return "chat"
    if _CHAT_LIKE_PATTERNS.search(stripped):
        return "chat"
    return "chat"


def _to_strands_messages(history: list[dict]) -> list[dict]:
    """Convert Redis message dicts to Strands Message format."""
    return [
        {"role": m["role"], "content": [{"type": "text", "text": m["content"]}]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


async def _load_context(
    session_id: str,
) -> tuple[str | None, list[dict], str | None, bool, list[dict], list[dict]]:
    """Fetch Redis history, inline attachments, image and data refs concurrently."""
    try:
        (summary, history), inline_text, has_rag, image_refs, data_refs = await asyncio.gather(
            memory.get_context(session_id),
            attachments.get_inline_text(session_id),
            attachments.has_rag_docs(session_id),
            attachments.get_image_refs(session_id),
            attachments.get_data_refs(session_id),
        )
    except Exception as exc:
        log.warning("load_context_fallback", session_id=session_id, error=str(exc))
        return (None, [], None, False, [], [])
    return (
        summary or None,
        _to_strands_messages(history),
        inline_text or None,
        has_rag,
        image_refs or [],
        data_refs or [],
    )


def _resolve_routing(message: str, agent_hint: str) -> tuple[str, bool, str | None]:
    """Apply agent_hint over the rule-based classifier."""
    hint = (agent_hint or "").strip().lower()
    if hint in VALID_AGENT_HINTS:
        if hint == "chat":
            return "chat", False, hint
        return "task", True, hint
    intent = _classify_intent(message)
    return intent, intent == "task", None


def _sse(event: dict) -> str:
    """Serialize a typed event as an SSE data frame."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _stream_agent(
    message: str,
    session_id: str,
    agent_hint: str = "",
    runtime_user: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Stream agent tokens, tool status events, and heartbeat frames over SSE."""
    loop = asyncio.get_event_loop()
    q: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    intent, enable_tools, effective_hint = _resolve_routing(message, agent_hint)
    log.info(
        "intent_classified",
        intent=intent,
        enable_tools=enable_tools,
        agent_hint=effective_hint,
        session_id=session_id,
        msg_preview=message[:60],
    )

    summary, strands_history, inline_text, has_rag, image_refs, data_refs = await _load_context(
        session_id
    )
    if has_rag or image_refs or data_refs:
        enable_tools = True

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
    seen_tool_ids: set[str] = set()

    def on_stream_event(**kwargs):
        """Forward Strands worker-thread callbacks into the async SSE queue."""
        current_tool = kwargs.get("current_tool_use")
        if current_tool:
            tool_id = str(current_tool.get("toolUseId") or "")
            if tool_id and tool_id not in seen_tool_ids:
                seen_tool_ids.add(tool_id)
                tool_name = current_tool.get("name", "unknown")
                tool_input = current_tool.get("input", {})
                log.info(
                    "tool_call",
                    tool=tool_name,
                    input_preview=str(tool_input)[:120],
                    session_id=session_id,
                )
                asyncio.run_coroutine_threadsafe(
                    q.put((
                        "status",
                        {
                            "tool": tool_name,
                            "input_preview": str(tool_input)[:200],
                        },
                    )),
                    loop,
                )
        token = kwargs.get("data")
        if token and isinstance(token, str):
            asyncio.run_coroutine_threadsafe(q.put(("token", token)), loop)

    def run_agent():
        """Run the blocking orchestrator in a worker thread."""
        callback_token = set_parent_callback(on_stream_event)
        runtime_token = set_runtime_user(runtime_user)
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
            clear_runtime_user(runtime_token)
            reset_parent_callback(callback_token)
            asyncio.run_coroutine_threadsafe(q.put(("done", "")), loop)

    threading.Thread(target=run_agent, daemon=True).start()

    start = loop.time()
    step_idx = 0
    timed_out = False
    while True:
        if loop.time() - start > _SSE_WALL_BUDGET_SEC:
            timed_out = True
            break
        try:
            kind, payload = await asyncio.wait_for(q.get(), timeout=_SSE_HEARTBEAT_SEC)
        except TimeoutError:
            yield ": keep-alive\n\n"
            continue

        if kind == "token":
            text = payload if isinstance(payload, str) else str(payload)
            full_reply.append(text)
            for ch in text:
                yield _sse({"type": "token", "text": ch})
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
        else:
            break

    if timed_out:
        log.warning(
            "agent_stream_wall_timeout",
            session_id=session_id,
            budget_sec=_SSE_WALL_BUDGET_SEC,
        )
        yield _sse({
            "type": "error",
            "message": f"Agent run exceeded {_SSE_WALL_BUDGET_SEC}s budget and was stopped",
        })

    yield _sse({"type": "done"})
    yield "data: [DONE]\n\n"

    reply_text = "".join(full_reply)
    await memory.append_message(session_id, "user", message)
    await memory.append_message(session_id, "assistant", reply_text)


async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    account_service: AccountService = Depends(get_account_service),
):
    """Run a streaming or non-streaming agent chat turn."""
    allowed, reason = account_service.check_quota(user["id"], "messages")
    if not allowed:
        raise HTTPException(status_code=402, detail=reason)
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
        account_service.consume_quota(user["id"], "messages")
        return StreamingResponse(
            _stream_agent(req.message, req.session_id, req.agent_hint, runtime_user=user),
            media_type="text/event-stream",
            headers={
                "X-Session-Id": req.session_id,
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    summary, strands_history, inline_text, has_rag, image_refs, data_refs = await _load_context(
        req.session_id
    )
    if has_rag or image_refs or data_refs:
        enable_tools = True
    loop = asyncio.get_event_loop()
    try:
        account_service.consume_quota(user["id"], "messages")

        def _invoke() -> str:
            """Invoke the blocking orchestrator for non-streaming chat."""
            runtime_token = set_runtime_user(user)
            try:
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
                return str(orchestrator(req.message))
            finally:
                clear_runtime_user(runtime_token)

        result = await loop.run_in_executor(None, _invoke)
        reply = str(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await memory.append_message(req.session_id, "user", req.message)
    await memory.append_message(req.session_id, "assistant", reply)
    return ChatResponse(session_id=req.session_id, reply=reply)
