"""SQLAlchemy model registry imports."""

# Import ORM models so Alembic sees them through Base.metadata.
from icore_agent.contexts.files.infrastructure.persistence.models import (  # noqa: E402,F401
    FileAssetRecord as FileAssetRecord,
)
from ..organizations.models import Organization as Organization  # noqa: E402,F401
from ..organizations.models import OrgMember as OrgMember  # noqa: E402,F401
from ..projects.models import Project as Project  # noqa: E402,F401
from ..projects.models import ProjectSession as ProjectSession  # noqa: E402,F401
from ..sessions.models import ChatSession as ChatSession  # noqa: E402,F401
from ..users.models import User as User  # noqa: E402,F401
from .base import Base

__all__ = [
    "Base",
    "ChatSession",
    "FileAssetRecord",
    "OrgMember",
    "Organization",
    "Project",
    "ProjectSession",
    "User",
]
