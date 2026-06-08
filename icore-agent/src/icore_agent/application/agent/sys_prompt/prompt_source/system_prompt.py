"""Base system prompts for agent runners."""

from __future__ import annotations

from enum import StrEnum


class PromptSource(StrEnum):
    """Known system prompt sources in the agent application layer."""

    ORCHESTRATOR = "orchestrator"


ORCHESTRATOR_SYSTEM_PROMPT_BASE = """
You are iCore Agent, an intelligent assistant running on the iCore enterprise platform.
The application layer has already made a coarse routing decision for this turn.
Your role is to use the available tools when the turn requires them and
synthesize their results into a final user-facing response.
""".strip()

_BASE_PROMPTS = {
    PromptSource.ORCHESTRATOR: ORCHESTRATOR_SYSTEM_PROMPT_BASE,
}


def coerce_prompt_source(prompt_source: PromptSource | str) -> PromptSource:
    """Return a known prompt source from a string or enum input."""
    if isinstance(prompt_source, PromptSource):
        return prompt_source
    return PromptSource(str(prompt_source).strip().lower())


def base_system_prompt(prompt_source: PromptSource | str) -> str:
    """Return the base system prompt for one prompt source."""
    return _BASE_PROMPTS[coerce_prompt_source(prompt_source)]
