from __future__ import annotations

from icore_agent.config import Settings


def test_litellm_kwargs_use_zai_base_url_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    monkeypatch.setenv("TIMEOUT_INTERVAL", "30")
    monkeypatch.setenv("MAX_RETRIES", "3")
    monkeypatch.delenv("MODEL_API_BASE", raising=False)

    settings = Settings(_env_file=None)

    kwargs = settings.litellm_kwargs()
    assert kwargs["api_base"] == "https://open.bigmodel.cn/api/paas/v4/"
    assert kwargs["timeout"] == 30
    assert kwargs["num_retries"] == 3


def test_settings_load_logging_service_domain(monkeypatch):
    monkeypatch.setenv("LOGGING_SERVICE_URL", "http://logging-service:8091")
    monkeypatch.setenv("LOGGING_SERVICE_TOKEN", "logging-token")
    monkeypatch.setenv("LOGGING_SERVICE_TIMEOUT", "2.5")

    settings = Settings(_env_file=None)

    assert settings.logging_service_url == "http://logging-service:8091"
    assert settings.logging_service_token == "logging-token"
    assert settings.logging_service_timeout == 2.5
