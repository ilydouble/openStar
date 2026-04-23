"""Research sub-agent — deep multi-source information synthesis.

Tools available to this agent:
  web_search    — search the public web
  fetch_webpage — download and read a full page in depth
  http_request  — call any REST API

Exposed as a Strands @tool so the orchestrator can delegate to it.
"""

import structlog
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands.tools.executors import SequentialToolExecutor

from ...config import settings
from ...tools.web_search import web_search
from ...tools.fetch_webpage import fetch_webpage
from ...tools.http_client import http_request
from ..callback_ctx import sub_agent_callback

log = structlog.get_logger()

# 单次研究任务内，各工具的最大调用次数。超过后 budgeted wrapper 会直接
# 返回一个告知 LLM 预算耗尽的字符串 —— 这是比 prompt 约束更可靠的硬闸门。
_BUDGETS = {"web_search": 3, "fetch_webpage": 5, "http_request": 3}

_SYSTEM_PROMPT = """
You are a research specialist. Given a research question or topic, you:
1. Break it into AT MOST 2–3 focused sub-questions (not 5+).
2. Use web_search to find relevant pages, then fetch_webpage to read the most
   promising one or two in depth.
3. Cross-verify key facts across sources before drawing conclusions.
4. Optionally call http_request to query structured REST APIs for data.
5. Synthesize a structured, citation-rich report.

## Hard tool budget per query (strict)
- web_search:    at most 3 calls total
- fetch_webpage: at most 5 calls total
- http_request:  at most 3 calls total

Once you have reached any of these limits, STOP calling that tool and write
the report from what you have. Partial evidence with clear caveats is
preferred over exhausting the API budget and failing with a rate-limit error.

If a tool returns an error (e.g. rate limited, timeout), do NOT retry it more
than once; move on and synthesize with the information already gathered.

Always return: Executive Summary → Key Findings → Sources → Confidence Level.
The Confidence Level should explicitly note any gaps caused by the budget.
""".strip()


def _make_budgeted_tools() -> list:
    """工厂：返回一组新 @tool，它们共享一个 budget 字典计数。

    每次创建 research agent 时重新调用，确保每个研究任务有独立的预算。
    """
    used = {"web_search": 0, "fetch_webpage": 0, "http_request": 0}

    def _over_budget(name: str) -> str:
        log.warning("research_budget_exceeded", tool=name,
                    used=used[name], limit=_BUDGETS[name])
        return (
            f"[BUDGET_EXCEEDED] '{name}' budget of {_BUDGETS[name]} reached "
            f"(used {used[name]} times). STOP calling this tool and write "
            f"the report from the information already gathered."
        )

    @tool(name="web_search")
    def web_search_budgeted(query: str, max_results: int = 5) -> str:
        """Search the web for up-to-date information.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return (1–10).
        """
        if used["web_search"] >= _BUDGETS["web_search"]:
            return _over_budget("web_search")
        used["web_search"] += 1
        return web_search(query=query, max_results=max_results)

    @tool(name="fetch_webpage")
    def fetch_webpage_budgeted(url: str) -> str:
        """Fetch the full text content of a webpage.

        Args:
            url: The full URL of the webpage to fetch.
        """
        if used["fetch_webpage"] >= _BUDGETS["fetch_webpage"]:
            return _over_budget("fetch_webpage")
        used["fetch_webpage"] += 1
        return fetch_webpage(url=url)

    @tool(name="http_request")
    def http_request_budgeted(
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        body: dict | str | None = None,
    ) -> str:
        """Make an HTTP request to any external REST API.

        Args:
            url: The full URL to call.
            method: HTTP method — GET, POST, PUT, PATCH, DELETE.
            headers: Optional dict of request headers.
            body: Optional request body; dict is serialized as JSON.
        """
        if used["http_request"] >= _BUDGETS["http_request"]:
            return _over_budget("http_request")
        used["http_request"] += 1
        return http_request(url=url, method=method, headers=headers, body=body)

    return [web_search_budgeted, fetch_webpage_budgeted, http_request_budgeted]


def _create_research_agent() -> Agent:
    model = LiteLLMModel(
        model_id=settings.model_id,
        params={
            "max_tokens": settings.agent_max_tokens,
            "temperature": 0.2,
            **settings.litellm_kwargs(),
        },
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=_make_budgeted_tools(),
        callback_handler=sub_agent_callback(),
        # 串行执行工具：避免一次回复里的多个 tool_use 被并发打到 Z.AI / 搜索
        # endpoint，瞬时 QPS 压爆 RPM 配额。
        tool_executor=SequentialToolExecutor(),
    )


@tool
def research_agent_tool(query: str) -> str:
    """Delegate a deep research task to the research sub-agent.

    Use this when the question requires multi-source synthesis, competitive
    analysis, or fact verification across several web sources.
    The research agent will search, fetch full pages, and synthesise results.

    Args:
        query: The research question or topic to investigate in depth.

    Returns:
        A structured research report with findings, citations, and confidence level.
    """
    agent = _create_research_agent()
    result = agent(query)
    return str(result)
