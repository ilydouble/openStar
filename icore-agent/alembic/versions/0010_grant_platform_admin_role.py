"""grant platform admin role to designated operator account

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_ADMIN_EMAIL = "turgut.sofuyev@gmail.com"


def upgrade() -> None:
    """Grant the platform admin role while preserving the owner role."""
    op.execute(
        f"""
        UPDATE users
        SET roles = '["owner", "admin"]'::jsonb
        WHERE lower(email) = lower('{_ADMIN_EMAIL}')
        """
    )


def downgrade() -> None:
    """Remove the platform admin role from the designated operator account."""
    op.execute(
        f"""
        UPDATE users
        SET roles = '["owner"]'::jsonb
        WHERE lower(email) = lower('{_ADMIN_EMAIL}')
        """
    )
