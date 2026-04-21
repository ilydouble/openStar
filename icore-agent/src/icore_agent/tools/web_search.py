"""Web search tool — backed by Tavily Search API.

Falls back to a DuckDuckGo scrape if TAVILY_API_KEY is not configured.
Exposed as a Strands @tool for use by the orchestrator and sub-agents.
"""

from __future__ import annotations

import structlog
import httpx
from strands import tool

from ..config import settings

log = structlog.get_logger()

_TAVILY_URL = "https://api.tavily.com/search"
_DDG_URL = "https://api.duckduckgo.com/"


def _tavily_search(query: str, max_results: int) -> list[dict]:
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }
    resp = httpx.post(_TAVILY_URL, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    answer = data.get("answer", "")
    formatted = []
    if answer:
        formatted.append({"title": "AI Answer", "url": "", "content": answer})
    for r in results[:max_results]:
        formatted.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:800],
        })
    return formatted


def _ddg_fallback(query: str, max_results: int) -> list[dict]:
    """DuckDuckGo Instant Answer API (no key required, limited)."""
    params = {"q": query, "format": "json", "no_redirect": "1"}
    resp = httpx.get(_DDG_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    results = []
    abstract = data.get("Abstract", "")
    if abstract:
        results.append({"title": data.get("Heading", ""), "url": data.get("AbstractURL", ""),
                        "content": abstract})
    for topic in data.get("RelatedTopics", [])[:max_results]:
        if isinstance(topic, dict) and "Text" in topic:
            results.append({"title": "", "url": topic.get("FirstURL", ""),
                            "content": topic.get("Text", "")[:400]})
    return results[:max_results]


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for up-to-date information.

    Uses Tavily (if configured) or DuckDuckGo as fallback.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (1–10).

    Returns:
        A formatted string with search results (title, URL, snippet).
    """
    max_results = min(max(1, max_results), 10)
    log.info("web_search", query=query, max_results=max_results)

    try:
        if settings.tavily_api_key:
            results = _tavily_search(query, max_results)
        else:
            log.warning("web_search_no_tavily_key", fallback="duckduckgo")
            results = _ddg_fallback(query, max_results)
    except Exception as exc:
        log.error("web_search_error", error=str(exc))
        return f"Search failed: {exc}"

    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        if r["url"]:
            lines.append(f"    URL: {r['url']}")
        lines.append(f"    {r['content']}")
    return "\n".join(lines)
