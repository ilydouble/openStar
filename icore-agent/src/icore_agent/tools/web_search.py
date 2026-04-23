"""Web search tool — backed by Tavily / Zhipu / DuckDuckGo.

Priority:
  1. Tavily       — if TAVILY_API_KEY is set  (best for English / global content)
  2. Zhipu Search — if ZAI_API_KEY is set     (best for Chinese content)
  3. DuckDuckGo   — no-key fallback           (limited, instant-answer only)

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
_ZHIPU_SEARCH_URL = "https://open.bigmodel.cn/api/paas/v4/web_search"


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


def _zhipu_search(query: str, max_results: int) -> list[dict]:
    """Zhipu web search API — reuses ZAI_API_KEY, supports Chinese content well.

    Docs: https://bigmodel.cn/dev/api/search/web-search
    Engine options (configured via settings.zhipu_search_engine):
      search_std        0.01¥/req  — standard, fast
      search_pro        0.03¥/req  — multi-engine, higher recall
      search_pro_sogou  0.05¥/req  — Sogou, covers Tencent ecosystem + Zhihu
      search_pro_quark  0.05¥/req  — Quark, precise vertical content
    """
    headers = {
        "Authorization": f"Bearer {settings.zai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "search_query": query,          # API 要求字段名为 search_query
        "search_engine": settings.zhipu_search_engine,
        "search_intent": False,         # False = 跳过意图识别，直接搜索（必填）
        "count": max_results,
    }
    resp = httpx.post(_ZHIPU_SEARCH_URL, json=payload, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    formatted = []
    for r in data.get("search_result", [])[:max_results]:
        formatted.append({
            "title": r.get("title", ""),
            "url": r.get("link", ""),
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

    Uses Tavily (if configured), Zhipu Search (if ZAI_API_KEY available),
    or DuckDuckGo as the final fallback.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (1–10).

    Returns:
        A formatted string with search results (title, URL, snippet).
    """
    max_results = min(max(1, max_results), 10)
    log.info("web_search", query=query, max_results=max_results)

    results: list[dict] = []
    last_error: Exception | None = None

    # ── 1. Tavily ──────────────────────────────────────────────────────────
    if settings.tavily_api_key:
        try:
            log.info("web_search_backend", backend="tavily")
            results = _tavily_search(query, max_results)
        except Exception as exc:
            log.warning("web_search_tavily_failed", error=str(exc), fallback="next")
            last_error = exc

    # ── 2. Zhipu Search ────────────────────────────────────────────────────
    if not results and settings.zai_api_key:
        try:
            log.info("web_search_backend", backend="zhipu",
                     engine=settings.zhipu_search_engine)
            results = _zhipu_search(query, max_results)
        except Exception as exc:
            log.warning("web_search_zhipu_failed", error=str(exc), fallback="duckduckgo")
            last_error = exc

    # ── 3. DuckDuckGo fallback ─────────────────────────────────────────────
    if not results:
        try:
            log.warning("web_search_backend", backend="duckduckgo")
            results = _ddg_fallback(query, max_results)
        except Exception as exc:
            log.error("web_search_all_failed", error=str(exc))
            return f"Search failed: {last_error or exc}"

    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        if r["url"]:
            lines.append(f"    URL: {r['url']}")
        lines.append(f"    {r['content']}")
    return "\n".join(lines)
