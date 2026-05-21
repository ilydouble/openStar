from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..sqlalchemy.base import Base

if TYPE_CHECKING:
    from ..organizations.models import Organization

RowIDType = BigInteger().with_variant(Integer(), "sqlite")


class Project(Base):
    """Persisted project metadata scoped to one organization."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("org_id", "public_id", name="uq_projects_org_public_id"),
    )

    id: Mapped[int] = mapped_column(RowIDType, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(120), nullable=False)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    sessions: Mapped[list["ProjectSession"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectSession(Base):
    """Workspace session metadata linked to a project and chat session id."""

    __tablename__ = "project_sessions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "session_public_id",
            name="uq_project_sessions_project_session",
        ),
    )

    id: Mapped[int] = mapped_column(RowIDType, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_public_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    project: Mapped[Project] = relationship(back_populates="sessions")
