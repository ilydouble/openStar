from __future__ import annotations

from ..base import DomainSettings

_DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173,http://localhost:3000"
)


def parse_cors_allowed_origins(raw: str) -> list[str]:
    """Split a comma-separated CORS origin list into normalized entries."""
    if not raw.strip():
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


class AppSettings(DomainSettings):
    env_domains = ("app",)

    app_name: str = "iCore Agent Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 11001
    cors_allowed_origins: str = _DEFAULT_CORS_ALLOWED_ORIGINS

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        """Return parsed browser origins allowed to call the API with credentials."""
        return parse_cors_allowed_origins(self.cors_allowed_origins)


app_settings = AppSettings()
