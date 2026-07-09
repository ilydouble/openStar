from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from icore_agent.infrastructure.persistence.sqlalchemy.base import Base

JsonObject = JSON().with_variant(JSONB(), "postgresql")
# SQLite only autoincrements INTEGER PRIMARY KEY; PostgreSQL keeps BIGINT.
UserIDType = BigInteger().with_variant(Integer(), "sqlite")


class User(Base):
    """Persisted account profile used by the account API."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        UserIDType, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True)
    user_name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan: Mapped[str] = mapped_column(
        String(40), nullable=False, default="trial")
    plan_label: Mapped[str] = mapped_column(
        String(80), nullable=False, default="Trial")
    organization_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True)
    organization_name: Mapped[str | None] = mapped_column(
        String(160), nullable=True)
    roles: Mapped[list[Any]] = mapped_column(
        JsonObject, nullable=False, default=list)
    byok: Mapped[dict[str, Any]] = mapped_column(
        JsonObject, nullable=False, default=dict)
    usage: Mapped[dict[str, Any]] = mapped_column(
        JsonObject, nullable=False, default=dict)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
