"""Main Strands Agents orchestrator — pure dispatch layer.

Architecture:
  User → Orchestrator (decides intent, selects the right sub-agent)
              ├─ research_agent_tool   → web research, multi-source synthesis
              │       ├─ web_search
              │       ├─ fetch_webpage
              │       └─ http_request
              ├─ code_agent_tool       → write / debug / run code
              │       ├─ run_python_snippet
              │       ├─ read_file
              │       └─ write_file  (+ sequential bash runner)
              └─ knowledge_agent_tool  → internal document RAG
                      ├─ chroma_search
                      └─ rerank_results

The Orchestrator itself holds NO direct primitive tools.
It only decides which sub-agent to delegate to, then synthesises
the sub-agent's reply into a final user-facing response.
"""

from typing import TYPE_CHECKING

import structlog
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager,
)

from ..config import settings
from .agents.research import research_agent_tool
from .agents.code import code_agent_tool
from .agents.knowledge import knowledge_agent_tool

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Type alias for clarity
Orchestrator = Agent

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


def _build_system_prompt(
    summary: str | None,
    attachments_text: str | None = None,
) -> str:
    """Combine base prompt with inline documents and conversation summary."""
    parts = [_SYSTEM_PROMPT_BASE]
    if attachments_text:
        parts.append(
            "## 用户上传的文档（直接阅读，无需调用工具）\n\n" + attachments_text
        )
    if summary:
        parts.append("## Earlier conversation summary\n" + summary)
    return "\n\n".join(parts)


def create_orchestrator(
    callback_handler=None,
    summary: str | None = None,
    attachments_text: str | None = None,
    enable_tools: bool = True,
) -> Orchestrator:
    """Factory — create a fresh orchestrator Agent via LiteLLM (no AWS needed).

    Args:
        callback_handler: 可选的 Strands 流式回调，用于 SSE 流式输出。
        summary:          Redis 滚动摘要，注入 system prompt。
                          近期原文历史由调用方预填充到 agent.messages。
        enable_tools:     是否挂载子 Agent 工具。纯聊天消息传 False，
                          可节省 token 并彻底杜绝不必要的工具调用。
    """
    model = LiteLLMModel(
        model_id=settings.model_id,
        params={
            "max_tokens": settings.agent_max_tokens,
            "temperature": settings.agent_temperature,
            **settings.litellm_kwargs(),
        },
    )

    # Window large enough to hold our pre-populated history (≤ memory_keep_recent=8)
    # plus the turns generated during this request; prevents Strands from
    # silently truncating messages we've deliberately kept.
    conversation_manager = SlidingWindowConversationManager(window_size=40)

    tools = (
        [research_agent_tool, code_agent_tool, knowledge_agent_tool]
        if enable_tools
        else []
    )

    orchestrator = Agent(
        model=model,
        system_prompt=_build_system_prompt(summary, attachments_text),
        callback_handler=callback_handler,
        conversation_manager=conversation_manager,
        tools=tools,
    )

    log.info(
        "orchestrator_created",
        model=settings.model_id,
        n_tools=len(tools),
        enable_tools=enable_tools,
    )
    return orchestrator
