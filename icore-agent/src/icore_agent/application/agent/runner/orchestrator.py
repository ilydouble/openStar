"""Strands Agent assembly for agent turns."""

from typing import Any

from strands import Agent
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager,
)
from strands.tools.executors import SequentialToolExecutor

from icore_agent.config import settings
from icore_agent.application.agent.sys_prompt import (
    BuildSystemPromptOptions,
    build_system_prompt,
)
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.application.agent.tool.tool_definition import make_agent_tool
from icore_agent.shared.logging.app_logger import get_logger

from .model_factory import create_litellm_model


log = get_logger(__name__)

# Type alias for clarity
Orchestrator = Any


def create_orchestrator(
    callback_handler=None,
    summary: str | None = None,
    session_id: str = "",
    hooks: list[Any] | None = None,
    user_id: str = "",
    user_memory_prompt: str | None = None,
    file_service: Any | None = None,
) -> Orchestrator:
    """Factory — create a fresh orchestrator Agent via LiteLLM (no AWS needed).

    Args:
        callback_handler:  可选的 Strands 流式回调，用于 SSE 流式输出。
        summary:           Redis 滚动摘要；不进入 system prompt。
        session_id:        注入到 scoped tools 的会话 ID。
        hooks:             Strands lifecycle hooks for application-level observers.
        user_id:           当前用户 public id，写入 LiteLLM metadata 以便 usage 回调记账。
        user_memory_prompt: 用户长期记忆片段；不进入 system prompt。
        file_service:      当前用户上传文件读取工具使用的文件服务。
    """
    selected_model = settings.effective_model_id()
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

    tool_definitions = build_orchestrator_tool_definitions(
        session_id=session_id,
        user_id=user_id,
        file_service=file_service,
    )
    system_prompt = str(build_system_prompt(BuildSystemPromptOptions(
        tools=tool_definitions,
    )))
    tools = [make_agent_tool(definition) for definition in tool_definitions]

    orchestrator = Agent(
        model=model,
        system_prompt=system_prompt,
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
    )
    return orchestrator
