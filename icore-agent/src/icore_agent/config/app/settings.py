from __future__ import annotations

from ..base import DomainSettings


class AppSettings(DomainSettings):
    app_name: str = "iCore Agent Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8080


app_settings = AppSettings()
