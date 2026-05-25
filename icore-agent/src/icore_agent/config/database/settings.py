from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pydantic import Field

from ..base import DomainSettings


class DatabaseSettings(DomainSettings):
    """Database-related settings loaded from the database dotenv domain."""

    env_domains = ("database",)

    db_host: str = "postgres"
    db_internal_port: int = Field(5432, ge=1, le=65535)
    db_host_port: int = Field(5432, ge=1, le=65535)
    db_user: str = "icore_agent"
    db_password: str = "change-me"
    db_name: str = "icore_agent_db"

    def __init__(self, **values: Any) -> None:
        """Initialize database settings from explicit values and domain env files."""
        super().__init__(**values)

    @property
    def sync_database_url(self) -> str:
        """Build the sync SQLAlchemy URL used by account repositories."""
        user = quote(self.db_user, safe="")
        password = quote(self.db_password, safe="")
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.db_host}:{self.db_internal_port}/{self.db_name}"
        )

    @property
    def database_url(self) -> str:
        """Build the async SQLAlchemy URL used by the runtime engine."""
        user = quote(self.db_user, safe="")
        password = quote(self.db_password, safe="")
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.db_host}:{self.db_internal_port}/{self.db_name}"
        )


database_settings = DatabaseSettings()
