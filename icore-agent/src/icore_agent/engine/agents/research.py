"""Research sub-agent — deep multi-source information synthesis.

Exposed as a Strands @tool so the orchestrator can call it like a function.
"""

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

from ...config import settings
from ...tools.web_search import web_search
from ...tools.http_client import http_request

_SYSTEM_PROMPT = """
You are a research specialist. Given a research question or topic, you:
1. Break it into specific sub-questions.
2. Search each sub-question using the available tools.
3. Cross-verify facts across multiple sources.
4. Synthesize a structured, citation-rich report.

Always return: Executive Summary → Key Findings → Sources → Confidence Level.
""".strip()


def _create_research_agent() -> Agent:
    model = LiteLLMModel(
        model_id=settings.model_id,
        max_tokens=settings.agent_max_tokens,
        temperature=0.2,
        **settings.litellm_kwargs(),
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[web_search, http_request],
    )


@tool
def research_agent_tool(query: str) -> str:
    """Delegate a deep research task to the research sub-agent.

    Use this when the question requires multi-source synthesis,
    competitive analysis, or fact verification across several searches.

    Args:
        query: The research question or topic to investigate in depth.

    Returns:
        A structured research report with findings and sources.
    """
    agent = _create_research_agent()
    result = agent(query)
    return str(result)
