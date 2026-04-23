"""Knowledge sub-agent — internal document retrieval and synthesis.

Architecture
------------
knowledge_agent_tool  (Strands @tool exposed to Orchestrator)
    └─ knowledge Agent (LLM)
           ├─ chroma_search   — vector search over uploaded documents
           └─ rerank_results  — lightweight keyword-overlap reranker

The agent calls chroma_search one or more times with refined queries,
optionally reranks the passages for better relevance ordering, and
synthesises a cited answer.  The LLM itself handles summarisation, so
no separate summarise tool is needed.
"""

from __future__ import annotations

import re
import json
from typing import Any
import structlog
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands.tools.executors import SequentialToolExecutor

from ...config import settings
from ...memory.chroma_store import search as _chroma_search_raw
from ..callback_ctx import sub_agent_callback

log = structlog.get_logger()

_SYSTEM_PROMPT = """
You are an internal knowledge specialist with access to the company's
uploaded documents, policies, manuals, and proprietary data.

Workflow:
1. Call chroma_search with a focused query.
2. If the first results are sparse, reformulate and search again (up to 3 times).
3. Use rerank_results to order retrieved passages by relevance if you have
   multiple results that vary in quality.
4. Synthesise all evidence into a clear, cited answer.
   — Cite the source filename and chunk index for every claim.
   — If no relevant passages are found after 3 searches, say so explicitly.

Never use external web knowledge; only use what the tools return.
""".strip()


# ── Rerank tool ────────────────────────────────────────────────────────────

@tool
def rerank_results(query: str, passages_json: str) -> str:
    """Rerank a list of retrieved passages by keyword-overlap relevance.

    Use this after chroma_search when multiple passages are returned and
    you want to surface the most relevant ones before synthesising.

    Args:
        query:         The original search query.
        passages_json: JSON array of passage strings (e.g. from chroma_search output).

    Returns:
        The same passages re-ordered from most to least relevant, as JSON.
    """
    try:
        passages: list[str] = json.loads(passages_json)
    except json.JSONDecodeError:
        return "[ERROR] passages_json must be a valid JSON array of strings."

    if not isinstance(passages, list):
        return "[ERROR] Expected a JSON array."

    # Keyword overlap score (token-level Jaccard-like)
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))

    def _score(passage: str) -> float:
        p_tokens = set(re.findall(r"[a-z0-9]+", passage.lower()))
        if not p_tokens:
            return 0.0
        return len(query_tokens & p_tokens) / len(query_tokens | p_tokens)

    ranked = sorted(passages, key=_score, reverse=True)
    return json.dumps(ranked, ensure_ascii=False)


# ── Sub-agent factory ──────────────────────────────────────────────────────

def _create_knowledge_agent(tenant_code: str = "") -> Agent:
    """Create a knowledge Agent with tenant_code baked into chroma_search.

    A scoped chroma_search tool is created dynamically so the sub-agent LLM
    never needs to supply or even know about tenant_code — it is captured
    in the closure and forwarded to every search call automatically.
    """
    # Scoped chroma_search: tenant_code is captured in closure, invisible to LLM.
    @tool
    def chroma_search(
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Search the internal knowledge base for relevant document passages.

        Call once for simple lookups; call multiple times with different focused
        queries for complex questions. Always cite the source filename.

        Args:
            query:   Natural-language question or search phrase.
            top_k:   Maximum number of passages to retrieve (default 5).
            filters: Optional metadata filter to narrow the search scope.
                     Use when the user mentions a specific document or file.
                     Examples:
                       {"filename": {"$eq": "employee_handbook.pdf"}}
                       {"filename": {"$eq": "policy_2024.pdf"}}
                     Leave as null to search across all documents.

        Returns:
            Formatted passages with source filenames and similarity scores,
            or a message stating no relevant documents were found.
        """
        try:
            results = _chroma_search_raw(
                query=query, tenant_code=tenant_code, top_k=top_k, filters=filters
            )
        except Exception as exc:
            log.warning("chroma_search_failed", error=str(exc), query=query[:80])
            return f"[Knowledge base search failed: {exc}]"

        if not results:
            return (
                "No relevant documents found in the knowledge base for this query. "
                "Try a different phrasing or confirm the topic is covered."
            )

        lines = [f"Found {len(results)} relevant passage(s):\n"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] Source: {r['source']} (chunk {r['chunk_index']}, "
                f"similarity {r['score']:.2f})\n{r['text']}"
            )
        return "\n\n".join(lines)

    model = LiteLLMModel(
        model_id=settings.model_id,
        params={
            "max_tokens": settings.agent_max_tokens,
            "temperature": 0.1,
            **settings.litellm_kwargs(),
        },
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[chroma_search, rerank_results],
        callback_handler=sub_agent_callback(),
        tool_executor=SequentialToolExecutor(),
    )


# ── Public tool exposed to Orchestrator ───────────────────────────────────

@tool
def knowledge_agent_tool(query: str, tenant_code: str = "") -> str:
    """Delegate an internal-knowledge question to the knowledge sub-agent.

    Use this when the user's question is likely answered by uploaded internal
    documents, company policies, product manuals, or proprietary data —
    NOT by the public web.

    The knowledge agent searches the document store with the correct tenant
    scope, reranks results for relevance, and returns a cited answer.

    Args:
        query:       The question or topic to look up in internal documents.
        tenant_code: Tenant identifier to scope the search (empty = shared KB).

    Returns:
        A cited answer based on retrieved internal document passages,
        or a clear statement that no relevant documents were found.
    """
    agent = _create_knowledge_agent(tenant_code)
    result = agent(query)
    return str(result)


__all__ = ["knowledge_agent_tool", "rerank_results"]
