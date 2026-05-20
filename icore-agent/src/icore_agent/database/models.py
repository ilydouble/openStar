"""SQLAlchemy model registry imports."""

# Import ORM models so Alembic sees them through Base.metadata.
from ..users.models import User as User  # noqa: E402,F401
from .base import Base

__all__ = ["Base", "User"]
