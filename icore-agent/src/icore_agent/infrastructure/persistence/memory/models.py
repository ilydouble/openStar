"""SQLAlchemy models for durable user memory."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..sqlalchemy.base import Base

JsonObject = JSON().with_variant(JSONB(), "postgresql")
FactIdType = BigInteger().with_variant(Integer(), "sqlite")


class UserMemoryProfileRecord(Base):
    """One durable memory profile row per user."""

    __tablename__ = "user_memory_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.public_id", ondelete="CASCADE"),
        primary_key=True,
    )
    profile: Mapped[dict[str, Any]] = mapped_column(
        JsonObject, nullable=False, default=dict)
    maintenance_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    extract_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    turns_since_extract: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    last_maintained_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class UserMemoryFactRecord(Base):
    """One structured memory fact owned by a user."""

    __tablename__ = "user_memory_facts"

    id: Mapped[int] = mapped_column(
        FactIdType, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.public_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active")
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="inferred")
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5)
    salience: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    access_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    last_accessed_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0)
    last_confirmed_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0)
    expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("user_memory_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_session_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
