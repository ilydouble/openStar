"""Unified system prompt builder for agent runners."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from icore_agent.application.agent.tool.tool_definition import ToolDefinition

from .prompt_source.system_prompt import (
    PromptSource,
    base_system_prompt,
    coerce_prompt_source,
)
from .prompt_source.tools import build_tools_prompt


@dataclass(frozen=True, slots=True)
class BuildSystemPromptOptions:
    """Options used to assemble the main agent system prompt."""

    prompt_source: PromptSource | str = PromptSource.ORCHESTRATOR
    tools: Sequence[ToolDefinition] = ()
    summary: str | None = None
    attachments_text: str | None = None
    user_memory_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class SystemPrompt:
    """Final system prompt text passed into a model-backed Agent."""

    text: str

    def __str__(self) -> str:
        """Return the prompt text for APIs that expect a plain string."""
        return self.text


def build_system_prompt(
    options: BuildSystemPromptOptions | None = None,
    **overrides: Any,
) -> SystemPrompt:
    """Build the final main-agent system prompt."""
    resolved = options or BuildSystemPromptOptions()
    if overrides:
        resolved = replace(resolved, **overrides)

    prompt_source = coerce_prompt_source(resolved.prompt_source)
    parts = [
        base_system_prompt(prompt_source),
        build_tools_prompt(resolved.tools),
    ]

    return SystemPrompt("\n\n".join(part for part in parts if part))
