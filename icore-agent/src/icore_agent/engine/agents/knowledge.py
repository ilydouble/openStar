"""Knowledge sub-agent — RAG retrieval from the tenant's knowledge base.

Currently uses a placeholder retriever; replace with your vector-DB client
(Bedrock Knowledge Bases, Milvus, PGVector, etc.).
"""

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

from ...config import settings
from ...tools.http_client import http_request

_SYSTEM_PROMPT = """
You are a knowledge retrieval specialist for the iCore platform.
You answer questions by retrieving relevant documents from the tenant's
knowledge base, then synthesising a precise, source-referenced answer.

Rules:
- Only use information retrieved from the knowledge base.
- If the answer is not found, say so clearly rather than hallucinating.
- Always cite the source document name and relevance score.
""".strip()


def _create_knowledge_agent() -> Agent:
    model = LiteLLMModel(
        model_id=settings.model_id,
        max_tokens=settings.agent_max_tokens,
        temperature=0.0,       # deterministic for RAG
        **settings.litellm_kwargs(),
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[http_request],  # calls the knowledge-base retrieval endpoint
    )


@tool
def knowledge_agent_tool(query: str, tenant_code: str = "") -> str:
    """Query the internal knowledge base and return a grounded answer.

    Use this when the user's question should be answered from internal documents,
    company policies, product manuals, or proprietary datasets — NOT from the web.

    Args:
        query: The natural-language question to answer from the knowledge base.
        tenant_code: Optional tenant identifier to scope the retrieval.

    Returns:
        A grounded answer with source citations from the knowledge base.
    """
    scoped_query = f"[tenant:{tenant_code}] {query}" if tenant_code else query
    agent = _create_knowledge_agent()
    result = agent(scoped_query)
    return str(result)
