"""Tiny structlog compatibility shim for lean test environments."""

from __future__ import annotations

import logging


class _CompatLogger:
    def __init__(self, name: str = "icore_agent") -> None:
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kwargs) -> None:
        if kwargs:
            self._logger.log(level, "%s | %s", event, kwargs)
        else:
            self._logger.log(level, "%s", event)

    def info(self, event: str, **kwargs) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        self._log(logging.WARNING, event, **kwargs)

    warn = warning

    def error(self, event: str, **kwargs) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def debug(self, event: str, **kwargs) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def exception(self, event: str, **kwargs) -> None:
        self._logger.exception("%s | %s", event, kwargs)

    def bind(self, **kwargs):
        return self


def get_logger(*args, **kwargs) -> _CompatLogger:
    name = args[0] if args else "icore_agent"
    return _CompatLogger(name)
