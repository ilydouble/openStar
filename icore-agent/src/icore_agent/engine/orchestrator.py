"""Main Strands Agents orchestrator — pure dispatch layer.

Architecture:
  User → Orchestrator (decides intent, selects the right sub-agent)
              ├─ research_agent_tool   → web research, multi-source synthesis
              ├─ code_agent_tool       → write / debug / run code
              ├─ knowledge_agent_tool  → internal document RAG
              ├─ image_agent_tool      → vision understanding + image generation
              └─ data_agent_tool       → pandas / SQL data analysis

The Orchestrator itself holds NO direct primitive tools.
It only decides which sub-agent to delegate to, then synthesises
the sub-agent's reply into a final user-facing response.
"""

from typing import TYPE_CHECKING

import structlog
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager,
)
from strands.tools.executors import SequentialToolExecutor

from ..config import settings
from .agents.research import research_agent_tool
from .agents.code import code_agent_tool
from .agents.knowledge import knowledge_agent_tool as _knowledge_agent_tool_raw
from .agents.image import image_agent_tool as _image_agent_tool_raw
from .agents.data import data_agent_tool

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Type alias for clarity
Orchestrator = Agent

# Valid agent hints coming from UI shortcut buttons.
VALID_AGENT_HINTS = {"research", "code", "knowledge", "image", "data", "chat"}

_SYSTEM_PROMPT_BASE = """
You are iCore Agent, an intelligent assistant running on the iCore enterprise platform.
Your role is to understand the user's intent and delegate to the right specialist:

## Sub-agents available

- research_agent_tool
    For: public web research, multi-source synthesis, competitive analysis,
         fact verification, fetching live data from URLs or REST APIs.
    NOT for: internal company documents.

- code_agent_tool
    For: writing, reviewing, debugging, or executing code; project scaffolding;
         reading / writing files in the workspace.
    Set use_sequential=True for multi-step bash tasks.

- knowledge_agent_tool
    For: questions answered by INTERNAL uploaded documents — company policies,
         product manuals, contracts, proprietary data.
    NOT for: general web knowledge.

- image_agent_tool
    For: analysing uploaded images (OCR, description, visual Q&A) OR
         generating new images from a text prompt (CogView-4).
    Pass image_source when the user uploaded an image or gave a URL.

- data_agent_tool
    For: tabular data analysis — CSV/Excel exploration, pandas transforms,
         SQL query drafting, aggregate statistics, outlier detection.
    Actually executes Python to compute real numbers.

## Dispatch rules
1. Classify the user's intent first; then call exactly the sub-agent that fits.
2. If multiple domains apply (e.g. "research the topic AND write code for it"),
   call sub-agents sequentially and combine their outputs.
3. For pure conversational replies (greetings, clarifications, simple reasoning)
   that require no tool use, respond directly without calling any sub-agent.
4. Always synthesise sub-agent results into a clear, user-facing final answer.
   Do not just forward raw tool output.
5. If a sub-agent's result is insufficient, try calling it again with a more
   refined query before giving up.
""".strip()


_HINT_DIRECTIVE = {
    "research": "The user clicked the Research shortcut — prefer research_agent_tool for this turn unless the request is clearly unrelated.",
    "code":     "The user clicked the Code shortcut — prefer code_agent_tool for this turn unless the request is clearly unrelated.",
    "knowledge":"The user clicked the Knowledge shortcut — prefer knowledge_agent_tool for this turn, scoped to their uploaded documents.",
    "image":    "The user clicked the Image shortcut — prefer image_agent_tool; if an image is attached, analyze it; otherwise generate one.",
    "data":     "The user clicked the Data shortcut — prefer data_agent_tool for tabular analysis, SQL drafting or pandas work.",
    "chat":     "The user clicked the Chat shortcut — answer directly as a conversational assistant; do not call any sub-agent.",
}


def _build_system_prompt(
    summary: str | None,
    attachments_text: str | None = None,
    image_attachments: list[dict] | None = None,
    data_attachments: list[dict] | None = None,
    agent_hint: str | None = None,
) -> str:
    """Combine base prompt with inline documents, images, data files and optional hint."""
    parts = [_SYSTEM_PROMPT_BASE]
    if agent_hint and agent_hint in _HINT_DIRECTIVE:
        parts.append("## Routing hint\n" + _HINT_DIRECTIVE[agent_hint])
    if attachments_text:
        parts.append(
            "## 用户上传的文档（直接阅读，无需调用工具）\n\n" + attachments_text
        )
    if image_attachments:
        lines = ["## 用户上传的图片（可通过 image_agent_tool 分析）"]
        for img in image_attachments:
            lines.append(
                f"- filename: `{img['filename']}`  ref: `{img['ref']}`"
            )
        lines.append(
            "需要分析时，调用 image_agent_tool 并传入 image_source=上面的 ref。"
        )
        parts.append("\n".join(lines))
    if data_attachments:
        lines = [
            "## 用户上传的数据文件（通过 data_agent_tool 用 pandas 真实计算）",
            "每个文件已落盘到服务器本地路径，可在 run_python_snippet 中直接 `pd.read_csv(abs_path)` / `pd.read_excel(abs_path)`。",
        ]
        for d in data_attachments:
            cols = ", ".join(
                f"{c['name']}({c['dtype']})" for c in (d.get("columns") or [])[:20]
            )
            rows = d.get("row_count")
            rows_txt = f"{rows} 行" if rows is not None else "行数未知"
            lines.append(
                f"\n### `{d['filename']}`\n"
                f"- abs_path: `{d['abs_path']}`\n"
                f"- size: {rows_txt}，{len(d.get('columns') or [])} 列\n"
                f"- columns: {cols or '(未解析)'}"
            )
            if d.get("preview_error"):
                lines.append(f"- preview_error: {d['preview_error']}")
            if d.get("preview_md"):
                lines.append(f"- head preview:\n\n{d['preview_md']}")
        lines.append(
            "\n分析这些文件时，请优先调用 data_agent_tool，并把具体问题连同 abs_path 一起传入。"
        )
        parts.append("\n".join(lines))
    if summary:
        parts.append("## Earlier conversation summary\n" + summary)
    return "\n\n".join(parts)


def _make_scoped_image_tool(session_id: str):
    """Bind session_id into image_agent_tool so the LLM doesn't have to pass it."""

    @tool
    def image_agent_tool(task: str, image_source: str = "") -> str:
        """Delegate a vision or image-generation task to the image sub-agent.

        Use this when the user asks to analyze / describe an uploaded image,
        or to draw / generate / create a new image from a text prompt.

        Args:
            task:         What to do with images (analyze or generate).
            image_source: Optional URL or session-scoped filename pointing to
                          an existing image to analyze.

        Returns:
            The image sub-agent's answer, including any image URL or markdown
            link to embed in the final reply.
        """
        return _image_agent_tool_raw(
            task=task, image_source=image_source, session_id=session_id
        )

    return image_agent_tool


def _make_scoped_knowledge_tool(session_id: str):
    """Bind session_id as tenant_code so LLM doesn't have to know it.

    Files attached via /attach are stored in ChromaDB under
    tenant_code=session_id; without this closure the LLM passes "" and hits
    the shared collection, missing every session-scoped upload.
    """

    @tool
    def knowledge_agent_tool(query: str) -> str:
        """Delegate an internal-knowledge question to the knowledge sub-agent.

        Use this when the user's question is likely answered by documents
        they uploaded in this session, company policies, product manuals or
        other internal proprietary data — NOT by the public web.

        Args:
            query: The question or topic to look up in internal documents.

        Returns:
            A cited answer based on retrieved internal document passages,
            or a clear statement that no relevant documents were found.
        """
        return _knowledge_agent_tool_raw(query=query, tenant_code=session_id)

    return knowledge_agent_tool


def create_orchestrator(
    callback_handler=None,
    summary: str | None = None,
    attachments_text: str | None = None,
    image_attachments: list[dict] | None = None,
    data_attachments: list[dict] | None = None,
    enable_tools: bool = True,
    agent_hint: str | None = None,
    session_id: str = "",
) -> Orchestrator:
    """Factory — create a fresh orchestrator Agent via LiteLLM (no AWS needed).

    Args:
        callback_handler:  可选的 Strands 流式回调，用于 SSE 流式输出。
        summary:           Redis 滚动摘要，注入 system prompt。
                           近期原文历史由调用方预填充到 agent.messages。
        attachments_text:  内联文档文本（40K 字符以内的小文件）。
        image_attachments: 会话内的图片附件引用列表，每项含 filename/ref。
        data_attachments:  会话内的结构化数据文件列表（CSV/Excel），含 abs_path +
                           schema + head 预览，交给 data_agent_tool 分析。
        enable_tools:      是否挂载子 Agent 工具。纯聊天消息传 False，
                           可节省 token 并彻底杜绝不必要的工具调用。
        agent_hint:        前端按钮传入的 agent 偏置（research/code/...）。
        session_id:        注入到 image_agent_tool 的会话 ID，用于生成图片存储路径。
    """
    # Pure-chat turns (enable_tools=False) go to the lighter fast model to
    # avoid paying glm-4.7's first-token latency for greetings and small talk.
    # Tool-enabled turns keep the flagship model for better reasoning / routing.
    selected_model = settings.model_id if enable_tools else (
        settings.model_id_fast or settings.model_id
    )
    model = LiteLLMModel(
    model_id=selected_model,
    params={
        "max_tokens": settings.agent_max_tokens,
        "temperature": settings.agent_temperature,
        "stream": True,  # 🔥 BUNU ƏLAVƏ ET
        **settings.litellm_kwargs(),
    },
)

    # Window large enough to hold our pre-populated history (≤ memory_keep_recent=8)
    # plus the turns generated during this request; prevents Strands from
    # silently truncating messages we've deliberately kept.
    conversation_manager = SlidingWindowConversationManager(window_size=40)

    if enable_tools:
        tools = [
            research_agent_tool,
            code_agent_tool,
            _make_scoped_knowledge_tool(session_id),
            _make_scoped_image_tool(session_id),
            data_agent_tool,
        ]
    else:
        tools = []

    orchestrator = Agent(
        model=model,
        system_prompt=_build_system_prompt(
            summary, attachments_text, image_attachments, data_attachments, agent_hint
        ),
        callback_handler=callback_handler,
        conversation_manager=conversation_manager,
        tools=tools,
        # 串行执行工具，避免一次回复里多个 tool_use 被并发打到 LLM 和搜索
        # endpoint，瞬时 QPS 压爆 Z.AI RPM 配额。
        tool_executor=SequentialToolExecutor(),
    )

    log.info(
        "orchestrator_created",
        model=selected_model,
        n_tools=len(tools),
        enable_tools=enable_tools,
        agent_hint=agent_hint,
    )
    return orchestrator
