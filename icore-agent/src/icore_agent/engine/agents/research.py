"""Research sub-agent — deep multi-source information synthesis.

Tools available to this agent:
  web_search    — search the public web
  fetch_webpage — download and read a full page in depth
  http_request  — call any REST API

Exposed as a Strands @tool so the orchestrator can delegate to it.
"""

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

from ...config import settings
from ...tools.web_search import web_search
from ...tools.fetch_webpage import fetch_webpage
from ...tools.http_client import http_request

_SYSTEM_PROMPT = """
You are a research specialist. Given a research question or topic, you:
1. Break it into specific sub-questions.
2. Use web_search to find relevant pages, then fetch_webpage to read them in depth.
3. Cross-verify facts across multiple sources before drawing conclusions.
4. Optionally call http_request to query structured REST APIs for data.
5. Synthesize a structured, citation-rich report.

Always return: Executive Summary → Key Findings → Sources → Confidence Level.
""".strip()


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
        tools=[web_search, fetch_webpage, http_request],
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
