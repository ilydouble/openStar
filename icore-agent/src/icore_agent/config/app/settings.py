from __future__ import annotations

from ..base import DomainSettings


class AppSettings(DomainSettings):
    env_domains = ("app",)

    app_name: str = "iCore Agent Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    backend_port_bind: str = "10001:8080"


app_settings = AppSettings()
