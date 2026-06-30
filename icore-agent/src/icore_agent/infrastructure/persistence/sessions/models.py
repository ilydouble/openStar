from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from ..sqlalchemy.base import Base

JsonObject = JSON().with_variant(JSONB(), "postgresql")
RowIDType = BigInteger().with_variant(Integer(), "sqlite")


class ChatSession(Base):
    """Persisted chat session owned by one account user."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    turns: Mapped[list[ChatTurn]] = relationship(
        back_populates="session",
        order_by="ChatTurn.id",
    )


class ChatTurn(Base):
    """One persisted execution turn inside a chat session."""

    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        RowIDType,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(
        JsonObject,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    usage: Mapped[dict[str, Any] | None] = mapped_column(
        JsonObject,
        nullable=True,
    )

    session: Mapped[ChatSession] = relationship(back_populates="turns")
    items: Mapped[list[ChatSessionItem]] = relationship(
        back_populates="turn",
        order_by="ChatSessionItem.sequence",
    )


class ChatSessionItem(Base):
    """One persisted domain item emitted during a chat turn."""

    __tablename__ = "session_items"
    __table_args__ = (
        UniqueConstraint("turn_id", "public_id",
                         name="uq_session_items_turn_public_id"),
        UniqueConstraint("turn_id", "sequence",
                         name="uq_session_items_turn_sequence"),
    )

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        RowIDType,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_id: Mapped[int] = mapped_column(
        RowIDType,
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(String(36), nullable=False)
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JsonObject,
        nullable=False,
        default=dict,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    session: Mapped[ChatSession] = relationship()
    turn: Mapped[ChatTurn] = relationship(back_populates="items")


class ChatSessionEvent(Base):
    """Append-only turn event record for stream replay and debugging."""

    __tablename__ = "session_events"
    __table_args__ = (
        UniqueConstraint("turn_id", "public_id",
                         name="uq_session_events_turn_public_id"),
        UniqueConstraint("turn_id", "sequence",
                         name="uq_session_events_turn_sequence"),
    )

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        RowIDType,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_id: Mapped[int] = mapped_column(
        RowIDType,
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    item_public_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JsonObject,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    session: Mapped[ChatSession] = relationship()
    turn: Mapped[ChatTurn] = relationship()
