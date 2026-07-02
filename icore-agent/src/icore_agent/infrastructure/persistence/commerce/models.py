"""SQLAlchemy model for Commerce diagnosis report snapshots."""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..sqlalchemy.base import Base

JsonObject = JSON().with_variant(JSONB(), "postgresql")
DiagnosisIDType = BigInteger().with_variant(Integer(), "sqlite")


class CommerceDiagnosisRecord(Base):
    """Persisted Commerce diagnosis report snapshot."""

    __tablename__ = "commerce_diagnoses"

    id: Mapped[int] = mapped_column(
        DiagnosisIDType, primary_key=True, autoincrement=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.public_id",
                   name="fk_commerce_diagnoses_user_id_users"),
        nullable=False,
        index=True,
    )
    agent_profile: Mapped[str] = mapped_column(String(80), nullable=False)
    source_file: Mapped[dict[str, Any]] = mapped_column(
        JsonObject, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JsonObject, nullable=False, default=dict)
    risks: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonObject, nullable=False, default=list)
    tasks: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonObject, nullable=False, default=list)
    report_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True)
