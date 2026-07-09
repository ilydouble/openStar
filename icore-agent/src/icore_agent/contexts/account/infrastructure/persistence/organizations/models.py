from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from icore_agent.infrastructure.persistence.sqlalchemy.base import Base

RowIDType = BigInteger().with_variant(Integer(), "sqlite")


class Organization(Base):
    """Persisted organization profile for team collaboration."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    knowledge_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="organization"
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    members: Mapped[list["OrgMember"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class OrgMember(Base):
    """Organization membership or invitation record."""

    __tablename__ = "org_members"
    __table_args__ = (
        UniqueConstraint("org_id", "member_public_id",
                         name="uq_org_members_org_member"),
    )

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[str] = mapped_column(
        String(40), nullable=False, default="viewer")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="members")
