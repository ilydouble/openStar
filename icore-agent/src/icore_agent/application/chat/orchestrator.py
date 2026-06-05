"""Strands Agent assembly for chat turns.

The application service resolves the high-level ChatRoutingDecision before this
factory is called. This module wires the selected model, conversation manager,
callback handler, and sub-agent tools into a Strands Agent. The LLM then decides
whether to call the available sub-agent tools during the turn.
"""

from typing import Any

from strands import Agent, tool
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager,
)
from strands.tools.executors import SequentialToolExecutor

from icore_agent.config import settings
from icore_agent.shared.logging.app_logger import get_logger

from .model_factory import create_litellm_model
from .prompts import build_orchestrator_system_prompt


log = get_logger(__name__)

# Type alias for clarity
Orchestrator = Any


def _make_scoped_image_tool(session_id: str):
    """Bind session_id into image_agent_tool so the LLM doesn't have to pass it."""
    from .agents.image import image_agent_tool as _image_agent_tool_raw

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

    Knowledge collections are scoped by tenant_code=session_id; without this
    closure the LLM passes "" and hits the shared collection.
    """
    from .agents.knowledge import knowledge_agent_tool as _knowledge_agent_tool_raw

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
    hooks: list[Any] | None = None,
    user_id: str = "",
    user_memory_prompt: str | None = None,
) -> Orchestrator:
    print(f"[DEBUG] create_orchestrator called: agent_hint={agent_hint!r}", flush=True)
    # Pi agent hint bypasses Strands entirely — delegate to pi-service.
    if (agent_hint or "").strip().lower() == "pi":
        from .agents.pi_agent import create_pi_orchestrator
        return create_pi_orchestrator(
            callback_handler=callback_handler,
            session_id=session_id,
            summary=summary,
        )
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
        hooks:             Strands lifecycle hooks for application-level observers.
        user_id:           当前用户 public id，写入 LiteLLM metadata 以便 usage 回调记账。
        user_memory_prompt: 用户长期记忆 prompt 片段。
    """
    # Pure-chat turns (enable_tools=False) go to the lighter fast model to
    # avoid paying glm-4.7's first-token latency for greetings and small talk.
    # Tool-enabled turns keep the flagship model for better reasoning / routing.
    primary_model = settings.effective_model_id()
    selected_model = primary_model if enable_tools else (
        settings.model_id_fast or primary_model
    )
    model = create_litellm_model(
        model_id=selected_model,
        max_tokens=settings.agent_max_tokens,
        temperature=settings.agent_temperature,
        user_id=user_id,
        session_id=session_id,
    )

    # Window large enough to hold our pre-populated history (≤ memory_keep_recent=8)
    # plus the turns generated during this request; prevents Strands from
    # silently truncating messages we've deliberately kept.
    conversation_manager = SlidingWindowConversationManager(window_size=40)

    if enable_tools:
        from .agents.code import code_agent_tool
        from .agents.data import data_agent_tool
        from .agents.research import research_agent_tool
        from .tools.number_comparator import number_comparator

        tools = [
            number_comparator,
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
        system_prompt=build_orchestrator_system_prompt(
            summary,
            attachments_text,
            image_attachments,
            data_attachments,
            agent_hint,
            user_memory_prompt,
        ),
        callback_handler=callback_handler,
        conversation_manager=conversation_manager,
        tools=tools,
        hooks=hooks or [],
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
