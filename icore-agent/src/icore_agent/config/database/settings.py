from __future__ import annotations

from urllib.parse import quote

from pydantic import Field

from ..base import DomainSettings


class DatabaseSettings(DomainSettings):
    env_domains = ("database",)

    db_host: str = "postgres"
    db_port: int = Field(5432, ge=1, le=65535)
    db_user: str = "icore_agent"
    db_password: str = "change-me"
    db_name: str = "icore_agent_db"

    @property
    def database_url(self) -> str:
        user = quote(self.db_user, safe="")
        password = quote(self.db_password, safe="")
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


database_settings = DatabaseSettings()
