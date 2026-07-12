from __future__ import annotations

from ..base import DomainSettings


class LoggingSettings(DomainSettings):
    """Settings for the internal Go logging-service client."""

    env_domains = ("logging",)

    logging_service_url: str = "http://logging-service:8091"
    logging_service_token: str = "dev-logging-service-token"
    logging_service_timeout: float = 2.0
    logging_client_drain_timeout: float = 5.0


logging_settings = LoggingSettings()
