from __future__ import annotations

from typing import Any

from pydantic import Field

from ..base import DomainSettings


class LLMSettings(DomainSettings):
    """LLM provider and model settings loaded from the llm dotenv domain."""

    env_domains = ("llm",)

    model_id: str = "zai/glm-4.7"
    model_id_fast: str = "zai/glm-4.7"
    model_api_base: str = ""
    zai_base_url: str = ""
    model_api_key: str = ""
    disable_thinking: bool = True
    timeout_interval: int = Field(30, ge=1, le=600)
    max_retries: int = Field(3, ge=0, le=10)
    agent_max_tokens: int = 8192
    agent_temperature: float = Field(0.1, ge=0.0, le=1.0)
    zai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    def __init__(self, **values: Any) -> None:
        """Initialize LLM settings from explicit values and domain env files."""
        super().__init__(**values)

    @staticmethod
    def _is_zai_model(model_id: str) -> bool:
        """Return whether the model id should use the Z.AI-compatible base URL."""
        model = model_id.strip().lower()
        return model.startswith("zai/") or model.startswith("glm-")

    def litellm_kwargs(self, model_id: str | None = None) -> dict:
        """Return extra parameters passed through to LiteLLM/Strands models."""
        kwargs: dict = {}
        if self.model_api_base:
            kwargs["api_base"] = self.model_api_base
        elif self.zai_base_url and self._is_zai_model(model_id or self.model_id):
            kwargs["api_base"] = self.zai_base_url
        if self.model_api_key:
            kwargs["api_key"] = self.model_api_key
        kwargs["timeout"] = self.timeout_interval
        kwargs["num_retries"] = self.max_retries
        if self.disable_thinking:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if self.model_id_fast and self.model_id_fast != self.model_id:
            kwargs["fallbacks"] = [self.model_id_fast]
        from icore_agent.lib.logging.app_logger import get_logger

        log = get_logger(__name__)
        log.info("litellm_kwargs_resolved", kwargs=kwargs)
        return kwargs


llm_settings = LLMSettings()
