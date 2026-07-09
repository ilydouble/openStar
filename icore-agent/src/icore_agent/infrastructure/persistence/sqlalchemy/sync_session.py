"""Synchronous SQLAlchemy session wiring for account repositories."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from icore_agent.config import settings

from .base import Base

_engine = None
_sessionmaker: sessionmaker[Session] | None = None


def sync_database_url() -> str:
    """Build the sync SQLAlchemy URL used by account repositories."""
    override = os.getenv("ICORE_TEST_SYNC_DATABASE_URL", "").strip()
    if override:
        return override
    return settings.sync_database_url


def get_sync_engine():
    """Create the sync engine lazily for account persistence."""
    global _engine
    if _engine is None:
        url = sync_database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {
        }
        engine_kwargs: dict = {"pool_pre_ping": True,
                               "connect_args": connect_args}
        if url.startswith("sqlite") and ":memory:" in url:
            from sqlalchemy.pool import StaticPool

            engine_kwargs["poolclass"] = StaticPool
        _engine = create_engine(url, **engine_kwargs)
    return _engine


def get_sync_sessionmaker() -> sessionmaker[Session]:
    """Create the sync session factory lazily."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(
            bind=get_sync_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _sessionmaker


def reset_sync_engine() -> None:
    """Reset the lazy sync engine so tests can point at a fresh database."""
    global _engine, _sessionmaker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None


def ensure_user_schema() -> None:
    """Create account and file tables when running against ephemeral test databases."""
    if os.getenv("ICORE_TEST_SYNC_DATABASE_URL", "").strip():
        from icore_agent.contexts.files.infrastructure.persistence.models import (  # noqa: F401
            FileAssetRecord,
        )
        from icore_agent.contexts.memory.infrastructure.persistence.models import (  # noqa: F401
            UserMemoryFactRecord,
            UserMemoryProfileRecord,
        )
        from icore_agent.contexts.account.infrastructure.persistence.organizations.models import Organization, OrgMember  # noqa: F401
        from ..payment_event_models import ProcessedPaymentEvent  # noqa: F401
        from icore_agent.contexts.account.infrastructure.persistence.projects.models import Project, ProjectSession  # noqa: F401
        from ..sessions.models import ChatSession  # noqa: F401
        from icore_agent.contexts.account.infrastructure.persistence.users.models import User  # noqa: F401

        Base.metadata.create_all(get_sync_engine())


@contextmanager
def sync_session_scope() -> Iterator[Session]:
    """Open a transactional sync session for one repository operation."""
    ensure_user_schema()
    session = get_sync_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
