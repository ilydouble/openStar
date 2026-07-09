"""SQLAlchemy models for processed payment integration events."""

from __future__ import annotations

from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from icore_agent.contexts.account.infrastructure.persistence.users.models import JsonObject

from .sqlalchemy.base import Base


class ProcessedPaymentEvent(Base):
    """Persist payment events that have already updated account entitlements."""

    __tablename__ = "processed_payment_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_no: Mapped[str] = mapped_column(String(64), nullable=False)
    user_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False)
    billing_period: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JsonObject,
        nullable=False,
        default=dict,
    )
    processed_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
