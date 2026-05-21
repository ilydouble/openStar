"""Async SQLAlchemy session wiring."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from icore_agent.config import settings

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """Create the async engine lazily so metadata imports stay side-effect free."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Create the async sessionmaker lazily from the shared engine."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one async database session from the lazily initialized factory."""
    async with get_sessionmaker()() as session:
        yield session
