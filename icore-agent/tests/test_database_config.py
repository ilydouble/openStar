from __future__ import annotations

from icore_agent.config import Settings, app_settings, database_settings, settings


def test_database_settings_build_async_url(monkeypatch):
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "icore_agent")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_NAME", "icore_agent_db")

    db_settings = Settings(_env_file=None)

    assert db_settings.db_host == "postgres"
    assert db_settings.db_port == 5432
    assert db_settings.db_user == "icore_agent"
    assert db_settings.db_password == "secret"
    assert db_settings.db_name == "icore_agent_db"
    assert (
        db_settings.database_url
        == "postgresql+asyncpg://icore_agent:secret@postgres:5432/icore_agent_db"
    )


def test_config_exports_domain_and_aggregate_settings():
    assert app_settings is settings
    assert database_settings.db_name == "icore_agent_db"
    assert settings.db_name == database_settings.db_name
