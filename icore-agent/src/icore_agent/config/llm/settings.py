from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import Field

from ..base import DomainSettings


@dataclass(frozen=True, slots=True)
class LiteLLMProviderSpec:
    """Map a LiteLLM model id prefix to provider-specific settings fields."""

    name: str
    model_prefixes: tuple[str, ...]
    api_key_attr: str
    base_url_attr: str | None = None

    def matches(self, model_id: str) -> bool:
        """Return whether this provider spec should configure the model id."""
        normalized = model_id.strip().lower()
        return any(normalized.startswith(prefix) for prefix in self.model_prefixes)


@dataclass(frozen=True, slots=True)
class ResolvedLiteLLMConfig:
    """LiteLLM configuration split between client and request parameters."""

    model_id: str
    client_args: dict[str, Any]
    params: dict[str, Any]

    def completion_kwargs(self) -> dict[str, Any]:
        """Return kwargs suitable for direct litellm completion calls."""
        return {
            "model": self.model_id,
            **self.client_args,
            **self.params,
        }


_LITELLM_PROVIDER_SPECS = (
    LiteLLMProviderSpec(
        name="zai",
        model_prefixes=("zai/", "glm-"),
        api_key_attr="zai_api_key",
        base_url_attr="zai_base_url",
    ),
    LiteLLMProviderSpec(
        name="openai",
        model_prefixes=("openai/", "gpt-", "chatgpt-", "o1", "o3", "o4-"),
        api_key_attr="openai_api_key",
    ),
    LiteLLMProviderSpec(
        name="anthropic",
        model_prefixes=("anthropic/", "claude-"),
        api_key_attr="anthropic_api_key",
    ),
)


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

    @staticmethod
    def _nonempty(value: Any) -> str:
        """Return a stripped string for settings values and payload fields."""
        return str(value or "").strip()

    def _provider_for_model(self, model_id: str) -> LiteLLMProviderSpec | None:
        """Return provider settings for a LiteLLM model id when known."""
        for spec in _LITELLM_PROVIDER_SPECS:
            if spec.matches(model_id):
                return spec
        return None

    def _runtime_byok(self) -> Mapping[str, Any]:
        """Return request-scoped BYOK settings when a runtime user is available."""
        try:
            from icore_agent.shared.runtime.user_context import current_runtime_user

            user = current_runtime_user()
        except Exception:
            return {}
        if user is None:
            return {}
        return user.byok or {}

    def _active_byok_for_model(self, model_id: str) -> Mapping[str, Any]:
        """Return active BYOK credentials when they match the selected model."""
        byok = self._runtime_byok()
        if not byok.get("enabled"):
            return {}
        byok_model = self._nonempty(byok.get("model"))
        if byok_model and byok_model == model_id:
            return byok
        return {}

    def _litellm_client_args(
        self,
        provider: LiteLLMProviderSpec | None,
        active_byok: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Resolve LiteLLM client arguments such as credentials and timeouts."""
        client_args: dict[str, Any] = {
            "timeout": self.timeout_interval,
            "num_retries": self.max_retries,
        }
        api_base = self._nonempty(active_byok.get("api_base"))
        api_key = self._nonempty(active_byok.get("api_key"))

        if not api_base:
            api_base = self._nonempty(self.model_api_base)
        if not api_base and provider is not None and provider.base_url_attr:
            api_base = self._nonempty(
                getattr(self, provider.base_url_attr, ""))

        if not api_key:
            api_key = self._nonempty(self.model_api_key)
        if not api_key and provider is not None:
            api_key = self._nonempty(getattr(self, provider.api_key_attr, ""))

        if api_base:
            client_args["api_base"] = api_base
        if api_key:
            client_args["api_key"] = api_key
        return client_args

    def _litellm_params(
        self,
        model_id: str,
        *,
        user_id: str | None,
        session_id: str | None,
        max_tokens: int | None,
        temperature: float | None,
        extra_params: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Resolve model request parameters for LiteLLM and Strands."""
        params: dict[str, Any] = {}
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if temperature is not None:
            params["temperature"] = temperature
        if self.disable_thinking and self._is_zai_model(model_id):
            params["extra_body"] = {"thinking": {"type": "disabled"}}
        if (
            self.model_id_fast
            and model_id == self.model_id
            and self.model_id_fast != self.model_id
        ):
            params["fallbacks"] = [self.model_id_fast]

        metadata = self._litellm_metadata(
            user_id=user_id,
            session_id=session_id,
        )
        if metadata:
            params["metadata"] = metadata
        params.setdefault("stream_options", {"include_usage": True})
        if extra_params:
            params.update(dict(extra_params))
        return params

    def _litellm_metadata(
        self,
        *,
        user_id: str | None,
        session_id: str | None,
    ) -> dict[str, str]:
        """Resolve usage metadata attached to LiteLLM requests."""
        metadata: dict[str, str] = {}
        resolved_user = self._nonempty(user_id)
        if not resolved_user:
            try:
                from icore_agent.shared.runtime.user_context import current_runtime_user

                runtime_user = current_runtime_user()
                if runtime_user is not None:
                    resolved_user = runtime_user.public_id
            except Exception:
                resolved_user = ""
        if resolved_user:
            metadata["user_id"] = resolved_user
        if session_id:
            metadata["session_id"] = session_id
        return metadata

    def resolve_litellm_config(
        self,
        model_id: str | None = None,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> ResolvedLiteLLMConfig:
        """Resolve provider credentials and request params for a model id."""
        resolved_model_id = self._nonempty(model_id) or self.model_id
        provider = self._provider_for_model(resolved_model_id)
        active_byok = self._active_byok_for_model(resolved_model_id)
        resolved = ResolvedLiteLLMConfig(
            model_id=resolved_model_id,
            client_args=self._litellm_client_args(
                provider,
                active_byok,
            ),
            params=self._litellm_params(
                resolved_model_id,
                user_id=user_id,
                session_id=session_id,
                max_tokens=max_tokens,
                temperature=temperature,
                extra_params=extra_params,
            ),
        )
        from icore_agent.shared.logging.app_logger import get_logger

        log = get_logger(__name__)
        log.info(
            "litellm_config_resolved",
            model_id=resolved.model_id,
            provider=provider.name if provider else None,
            client_args=resolved.client_args,
            params=resolved.params,
        )
        return resolved

    def litellm_kwargs(
        self,
        model_id: str | None = None,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> dict:
        """Return merged kwargs for direct litellm completion calls."""
        resolved = self.resolve_litellm_config(
            model_id=model_id,
            user_id=user_id,
            session_id=session_id,
            max_tokens=max_tokens,
            temperature=temperature,
            extra_params=extra_params,
        )
        return {
            **resolved.client_args,
            **resolved.params,
        }


llm_settings = LLMSettings()
