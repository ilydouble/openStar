"""chroma_search — Strands tool for querying the ChromaDB knowledge base.

Registered directly on the Orchestrator. For complex questions the Orchestrator
calls this tool multiple times with refined sub-queries and synthesises the
results itself, avoiding an extra LLM round-trip from a sub-agent.
"""

from __future__ import annotations

import structlog
from strands import tool

from ..memory.chroma_store import search as chroma_search_raw

log = structlog.get_logger()


@tool
def chroma_search(query: str, tenant_code: str = "", top_k: int = 5) -> str:
    """Search the internal knowledge base for documents relevant to a query.

    Use this when the user's question is likely answered by uploaded internal
    documents, company policies, product manuals, or proprietary data —
    NOT by the public web.

    Call this tool once for simple lookups. For complex questions, call it
    multiple times with different focused sub-queries, then synthesise the results.

    Args:
        query:       Natural-language question or search phrase.
        tenant_code: Tenant identifier to scope the search (use empty string
                     for the shared knowledge base).
        top_k:       Maximum number of document chunks to retrieve (default 5).

    Returns:
        Formatted string with retrieved passages and their source filenames.
        Returns a "no results" message if the knowledge base is empty or
        no relevant chunks are found.
    """
    try:
        results = chroma_search_raw(query=query, tenant_code=tenant_code, top_k=top_k)
    except Exception as exc:
        log.warning("chroma_search_failed", error=str(exc), query=query[:80])
        return f"[Knowledge base search failed: {exc}]"

    if not results:
        return (
            "No relevant documents found in the knowledge base for this query. "
            "The knowledge base may be empty or the topic may not be covered."
        )

    lines = [f"Found {len(results)} relevant passage(s):\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"[{i}] Source: {r['source']} (chunk {r['chunk_index']}, "
            f"similarity {r['score']:.2f})\n{r['text']}"
        )
    return "\n\n".join(lines)
