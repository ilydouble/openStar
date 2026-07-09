"""SQLAlchemy model registry imports."""

# Import ORM models so Alembic sees them through Base.metadata.
from icore_agent.contexts.files.infrastructure.persistence.models import (  # noqa: E402,F401
    FileAssetRecord as FileAssetRecord,
)
from icore_agent.contexts.account.infrastructure.persistence.organizations.models import (  # noqa: E402,F401
    Organization as Organization,
    OrgMember as OrgMember,
)
from icore_agent.contexts.account.infrastructure.persistence.projects.models import (  # noqa: E402,F401
    Project as Project,
    ProjectSession as ProjectSession,
)
from ..sessions.models import ChatSession as ChatSession  # noqa: E402,F401
from icore_agent.contexts.account.infrastructure.persistence.users.models import User as User  # noqa: E402,F401
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
