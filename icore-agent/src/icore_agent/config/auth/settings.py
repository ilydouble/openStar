from __future__ import annotations

from ..base import DomainSettings


class AuthSettings(DomainSettings):
    env_domains = ("auth",)

    icore_base_url: str = ""
    icore_secret: str = ""
    auth_enabled: bool = False


auth_settings = AuthSettings()
