"""Prompt fragments describing generic tool-use behavior."""

from __future__ import annotations

_TOOL_USE_RULES = """
## Tool-use rules
1. Use tools when they materially improve correctness, freshness, or access to external/local data.
2. For pure conversational replies that require no tool use, respond directly.
3. Combine tool results into a clear, user-facing final answer.
4. Do not expose raw tool output unless the user explicitly asks for it.
""".strip()


def build_tool_use_rules() -> str:
    """Build generic tool-use rules without listing tool schemas or names."""
    return _TOOL_USE_RULES
