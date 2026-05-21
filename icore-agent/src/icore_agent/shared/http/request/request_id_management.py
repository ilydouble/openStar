"""Request id extraction and generation helpers for inbound HTTP requests."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"
TRACEPARENT_HEADER = "traceparent"


def new_request_id() -> str:
    """Generate a compact request id for requests that arrive without one."""
    return uuid4().hex


def normalize_request_id(value: str | None) -> str | None:
    """Return a safe request id value or None when the header is empty/invalid."""
    if value is None:
        return None
    candidate = value.strip()
    if not candidate or "\r" in candidate or "\n" in candidate:
        return None
    return candidate


def trace_id_from_traceparent(value: str | None) -> str | None:
    """Extract the W3C trace id from a traceparent header when it is valid."""
    candidate = normalize_request_id(value)
    if candidate is None:
        return None

    parts = candidate.split("-")
    if len(parts) < 4:
        return None
    trace_id = parts[1]
    if len(trace_id) != 32 or trace_id == "0" * 32:
        return None
    if any(char not in "0123456789abcdefABCDEF" for char in trace_id):
        return None
    return trace_id.lower()


def request_id_from_headers(headers: Mapping[str, str]) -> str | None:
    """Resolve a request id from supported inbound headers without generating one."""
    request_id = normalize_request_id(_get_header(headers, REQUEST_ID_HEADER))
    if request_id is not None:
        return request_id

    correlation_id = normalize_request_id(
        _get_header(headers, CORRELATION_ID_HEADER))
    if correlation_id is not None:
        return correlation_id

    return trace_id_from_traceparent(_get_header(headers, TRACEPARENT_HEADER))


def resolve_request_id(headers: Mapping[str, str]) -> str:
    """Resolve an inbound request id or generate a backend-owned fallback id."""
    return request_id_from_headers(headers) or new_request_id()


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    """Read a header from case-insensitive Starlette headers or a plain mapping."""
    value = headers.get(name)
    if value is not None:
        return value
    return headers.get(name.lower())
