"""Domain rules for building the main agent system prompt."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any


class PromptSource(StrEnum):
    """Known base prompt sources for the main agent."""

    ORCHESTRATOR = "orchestrator"


ORCHESTRATOR_SYSTEM_PROMPT_BASE = """
You are iCore Agent, an intelligent assistant running on the iCore enterprise platform.
The application layer has already made a coarse routing decision for this turn.
Your role is to use the available tools when the turn requires them and
synthesize their results into a final user-facing response.
""".strip()

TOOL_USE_RULES = """
## Tool-use rules
1. Use tools when they materially improve correctness, freshness, or access to external/local data.
2. For pure conversational replies that require no tool use, respond directly.
3. Combine tool results into a clear, user-facing final answer.
4. Do not expose raw tool output unless the user explicitly asks for it.
""".strip()

_BASE_PROMPTS = {
    PromptSource.ORCHESTRATOR: ORCHESTRATOR_SYSTEM_PROMPT_BASE,
}


@dataclass(frozen=True, slots=True)
class BuildSystemPromptOptions:
    """Options used to assemble the main agent system prompt."""

    prompt_source: PromptSource | str = PromptSource.ORCHESTRATOR
    tools: Sequence[object] = ()
    summary: str | None = None
    user_memory_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class SystemPrompt:
    """Final system prompt text passed into a model-backed agent."""

    text: str

    def __str__(self) -> str:
        """Return the prompt text for APIs that expect a plain string."""
        return self.text


def coerce_prompt_source(prompt_source: PromptSource | str) -> PromptSource:
    """Return a known prompt source from a string or enum input."""
    if isinstance(prompt_source, PromptSource):
        return prompt_source
    return PromptSource(str(prompt_source).strip().lower())


def base_system_prompt(prompt_source: PromptSource | str) -> str:
    """Return the base system prompt for one prompt source."""
    return _BASE_PROMPTS[coerce_prompt_source(prompt_source)]


def build_tool_use_rules() -> str:
    """Build generic tool-use rules without listing tool schemas or names."""
    return TOOL_USE_RULES


def build_system_prompt(
    options: BuildSystemPromptOptions | None = None,
    **overrides: Any,
) -> SystemPrompt:
    """Build the final main-agent system prompt from pure domain rules."""
    resolved = options or BuildSystemPromptOptions()
    if overrides:
        resolved = replace(resolved, **overrides)

    prompt_source = coerce_prompt_source(resolved.prompt_source)
    parts = [
        base_system_prompt(prompt_source),
        build_tool_use_rules(),
    ]

    return SystemPrompt("\n\n".join(part for part in parts if part))
