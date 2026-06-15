"""Helpers for normalizing Strands tool-use and result payloads."""

from __future__ import annotations

import json
from typing import Any


def tool_call_id(tool_use: dict[str, Any]) -> str:
    """Extract a stable Strands tool-use id."""
    return str(tool_use.get("toolUseId") or "").strip()


def tool_name(tool_use: dict[str, Any]) -> str:
    """Extract a Strands tool name."""
    return str(tool_use.get("name") or "unknown").strip() or "unknown"


def tool_arguments(tool_use: dict[str, Any]) -> dict[str, Any]:
    """Extract JSON-safe tool arguments from a Strands toolUse payload."""
    raw_arguments = tool_use.get("input")
    if not isinstance(raw_arguments, dict):
        return {}
    return json_safe_object(raw_arguments)


def json_safe_object(value: Any) -> dict[str, Any]:
    """Return a JSON-compatible object, wrapped as a dict when needed."""
    normalized = json.loads(json_dumps(value))
    if isinstance(normalized, dict):
        return normalized
    return {"value": normalized}


def json_dumps(value: Any) -> str:
    """Serialize JSON content with stable separators for message content."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def result_text(result: dict[str, Any]) -> str | None:
    """Extract text from a Strands ToolResult payload."""
    content = result.get("content")
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("text"):
            return str(block["text"])
    return None
