"""Small backend logger facade that sends events directly to logging-service."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .contracts.v1 import LogLevel
from .logger import Logger, logger as default_logger
from .sanitizer import sanitize_for_logging_service

_BACKEND_SERVICE = "icore-backend"


class ServiceLogger:
    """ServiceLogger exposes module logging methods backed by logging-service."""

    def __init__(
        self,
        name: str,
        *,
        logger: Logger | None = None,
        now: Callable[[], datetime] | None = None,
        bound_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a backend logger for one module or component."""
        self.name = name
        self._logger = logger or default_logger
        self._now = now or (lambda: datetime.now(UTC))
        self._bound_metadata = bound_metadata or {}

    def bind(self, **metadata: Any) -> "ServiceLogger":
        """Return a logger with additional metadata included in every event."""
        return ServiceLogger(
            self.name,
            logger=self._logger,
            now=self._now,
            bound_metadata={**self._bound_metadata, **metadata},
        )

    def debug(self, message: str, **metadata: Any) -> bool:
        """Emit a DEBUG event when backend debug logging is enabled."""
        if not self._debug_enabled():
            return False
        return self._emit(LogLevel.DEBUG, message, metadata)

    def info(self, message: str, **metadata: Any) -> bool:
        """Emit an INFO event."""
        return self._emit(LogLevel.INFO, message, metadata)

    def warning(self, message: str, **metadata: Any) -> bool:
        """Emit a WARNING event."""
        return self._emit(LogLevel.WARNING, message, metadata)

    def error(self, message: str, **metadata: Any) -> bool:
        """Emit an ERROR event."""
        return self._emit(LogLevel.ERROR, message, metadata)

    def exception(self, message: str, **metadata: Any) -> bool:
        """Emit an ERROR event for exception handlers."""
        return self._emit(LogLevel.ERROR, message, metadata)

    def _emit(
        self,
        level: LogLevel,
        message: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Build and enqueue one logging-service event."""
        event_metadata = {
            "logger": self.name,
            **self._bound_metadata,
            **metadata,
        }
        sanitized = sanitize_for_logging_service(event_metadata)
        if not isinstance(sanitized, dict):
            sanitized = {"logger": self.name, "value": sanitized}
        try:
            return self._logger.emit_event(
                level,
                message=message,
                service=_BACKEND_SERVICE,
                metadata=sanitized,
                timestamp=self._now(),
            )
        except Exception as exc:  # noqa: BLE001 - logging must not break callers.
            print(
                f"[logging-service-fallback] backend logger emit failed: {exc}",
                file=sys.stderr,
            )
            return False

    @staticmethod
    def _debug_enabled() -> bool:
        """Return the runtime debug flag without creating config import cycles."""
        try:
            from icore_agent.config import settings

            return bool(settings.debug)
        except Exception:
            return False


def get_service_logger(
    name: str,
    *,
    logger: Logger | None = None,
    now: Callable[[], datetime] | None = None,
) -> ServiceLogger:
    """Return a module-scoped backend logger that writes to logging-service."""
    return ServiceLogger(name, logger=logger, now=now)
