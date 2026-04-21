"""Main Strands Agents orchestrator.

Architecture:
  User → Orchestrator (Strands Agent, LiteLLM model)
              ├─ web_search        (direct tool)
              ├─ http_request      (direct tool)
              ├─ research_agent    (sub-agent as tool)
              ├─ code_agent        (sub-agent as tool, wraps sequential runner)
              └─ knowledge_agent   (sub-agent as tool)
"""

from typing import TYPE_CHECKING

import structlog
from strands import Agent
from strands.models.litellm import LiteLLMModel

from ..config import settings
from ..tools.web_search import web_search
from ..tools.http_client import http_request
from .agents.research import research_agent_tool
from .agents.code import code_agent_tool
from .agents.knowledge import knowledge_agent_tool

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Type alias for clarity
Orchestrator = Agent

_SYSTEM_PROMPT = """
You are iCore Agent, an intelligent assistant running on the iCore enterprise platform.
You coordinate specialized sub-agents and tools to accomplish complex, multi-step tasks.

## Sub-agents (heavy, stateful, multi-step)
- research_agent   → Deep web research, multi-source synthesis, competitive analysis
- code_agent       → Write / debug / execute code; runs bash commands sequentially
- knowledge_agent  → Query the tenant's internal knowledge base via RAG

## Direct tools (fast, stateless)
- web_search       → Single keyword/question search (Tavily)
- http_request     → Call any external REST API

## Decision rules
1. Prefer direct tools for simple lookups; delegate to sub-agents for tasks needing
   multiple steps or domain expertise.
2. Always decompose complex user requests into sub-tasks before acting.
3. After each tool/sub-agent call, observe the result and decide the next step.
4. If a sub-agent fails, try an alternative approach rather than giving up.
5. Synthesize all intermediate results into a clear, well-structured final answer.
""".strip()


def create_orchestrator(callback_handler=None) -> Orchestrator:
    """Factory — create a fresh orchestrator Agent via LiteLLM (no AWS needed).

    Args:
        callback_handler: 可选的 Strands 流式回调，用于 SSE 流式输出。
                          回调会收到 data=<token> 等事件 kwargs。
    """
    model = LiteLLMModel(
        model_id=settings.model_id,
        max_tokens=settings.agent_max_tokens,
        temperature=settings.agent_temperature,
        **settings.litellm_kwargs(),
    )

    orchestrator = Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        callback_handler=callback_handler,
        tools=[
            web_search,
            http_request,
            research_agent_tool,
            code_agent_tool,
            knowledge_agent_tool,
        ],
    )

    log.info("orchestrator_created", model=settings.model_id, n_tools=5)
    return orchestrator
