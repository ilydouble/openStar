"""Model client protocol for provider-neutral agent loop sampling."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from icore_agent.contexts.agent.domain.prompt import PromptEnvelope

from .model_step import ModelStepResult, ModelStreamEvent


class ModelClient(Protocol):
    """Model client that samples a PromptEnvelope without executing tools."""

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Return one model step without executing any requested tools."""
        ...

    async def stream(
        self,
        envelope: PromptEnvelope,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Yield model text deltas and one final sampling result."""
        ...
