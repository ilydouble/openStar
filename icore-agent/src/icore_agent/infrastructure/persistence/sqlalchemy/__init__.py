from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import Base

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from .session import get_engine, get_session, get_sessionmaker

    AsyncSessionLocal: async_sessionmaker[AsyncSession]
    engine: AsyncEngine

__all__ = ["AsyncSessionLocal", "Base", "engine",
           "get_engine", "get_session", "get_sessionmaker"]


def __getattr__(name: str) -> Any:
    """Resolve runtime database objects lazily to avoid import-time side effects."""
    if name in {"AsyncSessionLocal", "engine", "get_engine", "get_session", "get_sessionmaker"}:
        from .session import get_engine, get_session, get_sessionmaker

        mapping = {
            "AsyncSessionLocal": get_sessionmaker(),
            "engine": get_engine(),
            "get_engine": get_engine,
            "get_session": get_session,
            "get_sessionmaker": get_sessionmaker,
        }
        return mapping[name]
    raise AttributeError(name)
