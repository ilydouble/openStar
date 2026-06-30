"""obsolete legacy tool-call projection migration

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-22
"""

from __future__ import annotations

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep the historical revision id without creating legacy projection tables."""


def downgrade() -> None:
    """No-op because this revision no longer creates any table."""
