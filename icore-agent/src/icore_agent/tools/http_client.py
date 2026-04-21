"""HTTP client tool — lets agents call arbitrary REST APIs.

Strands @tool wrapper around httpx.
"""

from __future__ import annotations

import json
import structlog
import httpx
from strands import tool

log = structlog.get_logger()

_TIMEOUT = 30  # seconds
_MAX_BODY_CHARS = 6_000


@tool
def http_request(
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

    Returns:
        Response status, headers summary, and body (truncated to 6000 chars).
    """
    method = method.upper()
    log.info("http_request", method=method, url=url)

    try:
        kwargs: dict = {"headers": headers or {}, "timeout": _TIMEOUT}

        if body is not None:
            if isinstance(body, dict):
                kwargs["json"] = body
                kwargs["headers"].setdefault("Content-Type", "application/json")
            else:
                kwargs["content"] = body.encode()

        with httpx.Client(follow_redirects=True) as client:
            resp = getattr(client, method.lower())(url, **kwargs)

        # Format response
        content_type = resp.headers.get("content-type", "")
        try:
            if "json" in content_type:
                body_str = json.dumps(resp.json(), ensure_ascii=False, indent=2)
            else:
                body_str = resp.text
        except Exception:
            body_str = resp.text

        if len(body_str) > _MAX_BODY_CHARS:
            body_str = body_str[:_MAX_BODY_CHARS] + "\n... [truncated]"

        return (
            f"Status: {resp.status_code}\n"
            f"Content-Type: {content_type}\n"
            f"Body:\n{body_str}"
        )

    except httpx.TimeoutException:
        return f"[TIMEOUT] Request to {url} timed out after {_TIMEOUT}s."
    except Exception as exc:
        log.error("http_request_error", error=str(exc))
        return f"[ERROR] {exc}"
