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
