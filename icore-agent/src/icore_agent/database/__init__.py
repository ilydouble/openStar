from .models import Base

__all__ = ["AsyncSessionLocal", "Base", "engine", "get_engine", "get_session", "get_sessionmaker"]


def __getattr__(name: str):
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
