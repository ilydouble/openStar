from __future__ import annotations

from icore_agent.config import Settings, app_settings, database_settings, settings
from icore_agent.config.base import dotenv_dir
from icore_agent.config.database import DatabaseSettings


def test_database_settings_build_async_url(monkeypatch):
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_INTERNAL_PORT", "5432")
    monkeypatch.setenv("DB_HOST_PORT", "15432")
    monkeypatch.setenv("DB_USER", "icore_agent")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_NAME", "icore_agent_db")

    db_settings = Settings(_env_file=None)

    assert db_settings.db_host == "postgres"
    assert db_settings.db_internal_port == 5432
    assert db_settings.db_host_port == 15432
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


def test_settings_load_split_dotenv_files(tmp_path, monkeypatch):
    dotenv_dir = tmp_path / "dotenv"
    dotenv_dir.mkdir()
    (dotenv_dir / ".env.app").write_text(
        "APP_NAME=Split Env App\nAPI_PORT=11001\n",
        encoding="utf-8",
    )
    (dotenv_dir / ".env.database").write_text(
        "\n".join(
            [
                "DB_HOST=db.example",
                "DB_INTERNAL_PORT=15432",
                "DB_HOST_PORT=25432",
                "DB_USER=split_user",
                "DB_PASSWORD=split_secret",
                "DB_NAME=split_db",
            ]
        ),
        encoding="utf-8",
    )
    (dotenv_dir / ".env.llm").write_text(
        "MODEL_ID=zai/glm-4.7\nTIMEOUT_INTERVAL=12\nMAX_RETRIES=2\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("ICORE_AGENT_DOTENV_DIR", str(dotenv_dir))
    for key in (
        "APP_NAME",
        "API_PORT",
        "DB_HOST",
        "DB_INTERNAL_PORT",
        "DB_HOST_PORT",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
        "MODEL_ID",
        "TIMEOUT_INTERVAL",
        "MAX_RETRIES",
    ):
        monkeypatch.delenv(key, raising=False)

    split_settings = Settings()

    assert split_settings.app_name == "Split Env App"
    assert split_settings.api_port == 11001
    assert split_settings.db_host == "db.example"
    assert split_settings.db_internal_port == 15432
    assert split_settings.db_host_port == 25432
    assert split_settings.model_id == "zai/glm-4.7"
    assert split_settings.timeout_interval == 12
    assert split_settings.max_retries == 2


def test_default_dotenv_dir_resolves_to_dotenv(monkeypatch):
    """Local process defaults should load the dotenv directory directly."""
    monkeypatch.delenv("ICORE_AGENT_DOTENV_DIR", raising=False)

    assert dotenv_dir().name == "dotenv"


def test_domain_settings_load_only_their_dotenv_file(tmp_path, monkeypatch):
    dotenv_dir = tmp_path / "dotenv"
    dotenv_dir.mkdir()
    (dotenv_dir / ".env.database").write_text("DB_NAME=domain_db\n", encoding="utf-8")
    (dotenv_dir / ".env.llm").write_text("MODEL_ID=domain/model\n", encoding="utf-8")

    monkeypatch.setenv("ICORE_AGENT_DOTENV_DIR", str(dotenv_dir))
    monkeypatch.delenv("DB_NAME", raising=False)

    db_settings = DatabaseSettings()

    assert db_settings.db_name == "domain_db"
