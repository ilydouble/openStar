"""Factory helpers for chat-layer LiteLLM models."""

from __future__ import annotations

from strands.models.litellm import LiteLLMModel

from icore_agent.config import settings


def create_litellm_model(
    *,
    model_id: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> LiteLLMModel:
    """Create a Strands LiteLLM model from resolved application settings."""
    selected_model = model_id or settings.effective_model_id()
    resolved = settings.resolve_litellm_config(
        model_id=selected_model,
        user_id=user_id,
        session_id=session_id,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return LiteLLMModel(
        client_args=resolved.client_args,
        model_id=resolved.model_id,
        params=resolved.params,
    )
