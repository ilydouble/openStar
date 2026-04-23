"""fetch_webpage — download a URL and return its plain text.

Strips HTML tags, collapses whitespace, and truncates to a safe token
budget so the content fits inside a context window.

Used by research_agent to read full page content after a web_search
returns a promising URL.
"""

from __future__ import annotations

import re
import structlog
import httpx
from strands import tool

log = structlog.get_logger()

_TIMEOUT = 20          # seconds
_MAX_CHARS = 12_000    # ~3 k tokens — enough for dense synthesis
_USER_AGENT = (
    "Mozilla/5.0 (compatible; iCoreAgent/1.0; +https://icore.ai/bot)"
)


def _strip_html(html: str) -> str:
    """Very lightweight HTML → plain-text conversion (no external deps)."""
    # Remove <script> and <style> blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                  flags=re.IGNORECASE | re.DOTALL)
    # Remove all remaining tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    for entity, char in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        html = html.replace(entity, char)
    # Collapse whitespace
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


@tool
def fetch_webpage(url: str) -> str:
    """Fetch the full text content of a webpage.

    Use this AFTER web_search to read a specific page in depth when the
    search snippet is not sufficient to answer the question.

    Args:
        url: The full URL of the webpage to fetch.

    Returns:
        Plain text extracted from the page (up to ~12 000 characters),
        or an error message if the page cannot be retrieved.
    """
    log.info("fetch_webpage", url=url)

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type or "text/plain" in content_type:
            text = _strip_html(resp.text) if "html" in content_type else resp.text
        else:
            return f"[SKIPPED] Non-text content-type: {content_type}"

        if len(text) > _MAX_CHARS:
            text = text[:_MAX_CHARS] + f"\n\n... [page truncated at {_MAX_CHARS} chars]"

        return f"URL: {url}\n\n{text}"

    except httpx.HTTPStatusError as exc:
        return f"[HTTP {exc.response.status_code}] {url}"
    except httpx.TimeoutException:
        return f"[TIMEOUT] Could not fetch {url} within {_TIMEOUT}s."
    except Exception as exc:
        log.warning("fetch_webpage_error", url=url, error=str(exc))
        return f"[ERROR] {exc}"
