from __future__ import annotations

from icore_agent.config import Settings
from icore_agent.contexts.account.domain.user import AuthenticatedUser
from icore_agent.shared.runtime.user_context import clear_runtime_user, set_runtime_user


def test_resolve_litellm_config_splits_zai_client_args_and_params(monkeypatch):
    """Z.AI credentials should be resolved into LiteLLM client_args."""
    monkeypatch.setenv("MODEL_ID", "zai/glm-4.7")
    monkeypatch.setenv("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    monkeypatch.setenv("ZAI_API_KEY", "zai-key")
    monkeypatch.setenv("TIMEOUT_INTERVAL", "30")
    monkeypatch.setenv("MAX_RETRIES", "3")
    monkeypatch.setenv("DISABLE_THINKING", "true")
    monkeypatch.delenv("MODEL_API_BASE", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    resolved = settings.resolve_litellm_config(
        user_id="user-1",
        session_id="session-1",
        max_tokens=1024,
        temperature=0.2,
    )

    assert resolved.model_id == "zai/glm-4.7"
    assert resolved.client_args["api_base"] == "https://open.bigmodel.cn/api/paas/v4/"
    assert resolved.client_args["api_key"] == "zai-key"
    assert resolved.client_args["timeout"] == 30
    assert resolved.client_args["num_retries"] == 3
    assert resolved.params["max_tokens"] == 1024
    assert resolved.params["temperature"] == 0.2
    assert resolved.params["metadata"] == {
        "user_id": "user-1",
        "session_id": "session-1",
    }
    assert resolved.params["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "api_key" not in resolved.params


def test_default_glm_51_config_enables_thinking(monkeypatch):
    """Default Z.AI requests should explicitly enable GLM-5.1 thinking."""
    monkeypatch.delenv("MODEL_ID", raising=False)
    monkeypatch.delenv("MODEL_ID_FAST", raising=False)
    monkeypatch.delenv("DISABLE_THINKING", raising=False)

    settings = Settings(_env_file=None)
    resolved = settings.resolve_litellm_config()

    assert settings.model_id == "zai/glm-5.1"
    assert settings.model_id_fast == "zai/glm-5.1"
    assert settings.disable_thinking is False
    assert resolved.params["extra_body"] == {
        "thinking": {
            "type": "enabled",
            "clear_thinking": True,
        },
    }


def test_litellm_kwargs_keeps_direct_completion_compatibility(monkeypatch):
    """The legacy helper should still return flat LiteLLM completion kwargs."""
    monkeypatch.setenv("MODEL_ID", "zai/glm-4.7")
    monkeypatch.setenv("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    monkeypatch.setenv("ZAI_API_KEY", "zai-key")
    monkeypatch.setenv("TIMEOUT_INTERVAL", "30")
    monkeypatch.setenv("MAX_RETRIES", "3")
    monkeypatch.delenv("MODEL_API_BASE", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    kwargs = settings.litellm_kwargs()
    assert kwargs["api_base"] == "https://open.bigmodel.cn/api/paas/v4/"
    assert kwargs["api_key"] == "zai-key"
    assert kwargs["timeout"] == 30
    assert kwargs["num_retries"] == 3


def test_resolve_litellm_config_prefers_generic_model_override(monkeypatch):
    """MODEL_API_* should override provider-specific platform credentials."""
    monkeypatch.setenv("MODEL_API_BASE", "https://relay.example.com/v1")
    monkeypatch.setenv("MODEL_API_KEY", "relay-key")
    monkeypatch.setenv("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    monkeypatch.setenv("ZAI_API_KEY", "zai-key")

    settings = Settings(_env_file=None)

    resolved = settings.resolve_litellm_config(model_id="zai/glm-4.7")

    assert resolved.client_args["api_base"] == "https://relay.example.com/v1"
    assert resolved.client_args["api_key"] == "relay-key"


def test_resolve_litellm_config_uses_provider_key_by_model_id(monkeypatch):
    """Known model prefixes should select the matching provider API key."""
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.delenv("MODEL_API_BASE", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    openai = settings.resolve_litellm_config(model_id="openai/gpt-4o-mini")
    anthropic = settings.resolve_litellm_config(
        model_id="anthropic/claude-3-5-sonnet"
    )

    assert openai.client_args["api_key"] == "openai-key"
    assert anthropic.client_args["api_key"] == "anthropic-key"
    assert "extra_body" not in openai.params
    assert "extra_body" not in anthropic.params


def test_resolve_litellm_config_prefers_active_byok_credentials(monkeypatch):
    """Active runtime BYOK settings should drive model and client credentials."""
    monkeypatch.setenv("MODEL_API_KEY", "platform-key")
    settings = Settings(_env_file=None)
    token = set_runtime_user(
        AuthenticatedUser(
            public_id="user-1",
            email="user@example.com",
            name="User",
            byok={
                "enabled": True,
                "model": "openai/gpt-4o-mini",
                "api_key": "byok-key",
                "api_base": "https://byok.example.com/v1",
            },
        )
    )
    try:
        resolved = settings.resolve_litellm_config(
            model_id=settings.effective_model_id()
        )
    finally:
        clear_runtime_user(token)

    assert resolved.model_id == "openai/gpt-4o-mini"
    assert resolved.client_args["api_key"] == "byok-key"
    assert resolved.client_args["api_base"] == "https://byok.example.com/v1"


def test_settings_load_logging_service_domain(monkeypatch):
    monkeypatch.setenv("LOGGING_SERVICE_URL", "http://logging-service:8091")
    monkeypatch.setenv("LOGGING_SERVICE_TOKEN", "logging-token")
    monkeypatch.setenv("LOGGING_SERVICE_TIMEOUT", "2.5")
    monkeypatch.setenv("LOGGING_CLIENT_DRAIN_TIMEOUT", "6.5")
    monkeypatch.setenv("LOGGING_CLIENT_BATCH_FLUSH_MS", "125")
    monkeypatch.setenv("LOGGING_CLIENT_MAX_BATCH_SIZE", "32")

    settings = Settings(_env_file=None)

    assert settings.logging_service_url == "http://logging-service:8091"
    assert settings.logging_service_token == "logging-token"
    assert settings.logging_service_timeout == 2.5
    assert settings.logging_client_drain_timeout == 6.5
    assert settings.logging_client_batch_flush_ms == 125
    assert settings.logging_client_max_batch_size == 32


def test_settings_load_agent_runtime_domain(monkeypatch):
    """Agent runtime settings should be part of aggregate settings."""
    monkeypatch.setenv("AGENT_RUNTIME_LOCK_TTL_SECONDS", "42")
    monkeypatch.setenv("AGENT_RUNTIME_STATE_TTL_SECONDS", "84")

    settings = Settings(_env_file=None)

    assert settings.agent_runtime_lock_ttl_seconds == 42
    assert settings.agent_runtime_state_ttl_seconds == 84


def test_settings_load_agent_tool_workspace_from_tools_domain(monkeypatch):
    """Agent tool workspace belongs to the tools settings domain."""
    monkeypatch.setenv("AGENT_TOOL_WORKSPACE", "/tmp/icore-agent-tools")

    settings = Settings(_env_file=None)

    assert settings.agent_tool_workspace == "/tmp/icore-agent-tools"
