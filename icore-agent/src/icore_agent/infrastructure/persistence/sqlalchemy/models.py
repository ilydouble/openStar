"""SQLAlchemy model registry imports."""

# Import ORM models so Alembic sees them through Base.metadata.
from ..files.models import FileAssetRecord as FileAssetRecord  # noqa: E402,F401
from ..users.models import User as User  # noqa: E402,F401
from .base import Base

__all__ = ["Base", "FileAssetRecord", "User"]
