"""SQLAlchemy model registry imports."""

from .base import Base


# Import ORM models so Alembic sees them through Base.metadata.
from ..users.models import User as User  # noqa: E402,F401
