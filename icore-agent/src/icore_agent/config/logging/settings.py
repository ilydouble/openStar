from __future__ import annotations

from ..base import DomainSettings


class LoggingSettings(DomainSettings):
    """Settings for the internal Go logging-service client."""

    env_domains = ("logging",)

    logging_service_url: str = "http://127.0.0.1:18091"
    logging_service_token: str = "dev-logging-service-token"
    logging_service_timeout: float = 2.0


logging_settings = LoggingSettings()
