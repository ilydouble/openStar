from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session",
        order_by="ChatMessage.sequence",
    )
    turns: Mapped[list[ChatTurn]] = relationship(
        back_populates="session",
        order_by="ChatTurn.id",
    )


class ChatMessage(Base):
    """One persisted chat turn within a session."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence",
                         name="uq_messages_session_sequence"),
    )

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JsonObject,
        nullable=False,
        default=dict,
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class LlmToolCall(Base):
    """One persisted LLM tool invocation and its JSON result."""

    __tablename__ = "llm_tool_calls"

    id: Mapped[int] = mapped_column(
        RowIDType, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        RowIDType,
        ForeignKey(
            "sessions.id",
            name="fk_llm_tool_calls_session_id_sessions",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    assistant_message_id: Mapped[int | None] = mapped_column(
        RowIDType,
        ForeignKey(
            "messages.id",
            name="fk_llm_tool_calls_assistant_message_id_messages",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    tool_message_id: Mapped[int | None] = mapped_column(
        RowIDType,
        ForeignKey(
            "messages.id",
            name="fk_llm_tool_calls_tool_message_id_messages",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    tool_call_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    tool_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="function")
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(
        JsonObject,
        nullable=False,
        default=dict,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JsonObject,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
