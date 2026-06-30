"""create processed payment events

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_payment_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("order_no", sa.String(length=64), nullable=False),
        sa.Column("user_public_id", sa.String(length=64), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("billing_period", sa.String(length=16), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_processed_payment_events_user_processed_at",
        "processed_payment_events",
        ["user_public_id", "processed_at"],
    )
    op.create_index(
        "ix_processed_payment_events_order_id",
        "processed_payment_events",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processed_payment_events_order_id",
        table_name="processed_payment_events",
    )
    op.drop_index(
        "ix_processed_payment_events_user_processed_at",
        table_name="processed_payment_events",
    )
    op.drop_table("processed_payment_events")
