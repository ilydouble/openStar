"""create organizations, members, and projects tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "knowledge_scope",
            sa.String(length=32),
            nullable=False,
            server_default="organization",
        ),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.public_id"],
            name="fk_organizations_owner_user_id",
        ),
        sa.UniqueConstraint("public_id", name="uq_organizations_public_id"),
    )
    op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"])

    op.create_table(
        "org_members",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("member_public_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=40), nullable=False, server_default="viewer"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name="fk_org_members_org_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.public_id"],
            name="fk_org_members_user_id",
        ),
        sa.UniqueConstraint("org_id", "member_public_id", name="uq_org_members_org_member"),
    )
    op.create_index("ix_org_members_org_id", "org_members", ["org_id"])
    op.create_index("ix_org_members_user_id", "org_members", ["user_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.String(length=120), nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("scenario_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name="fk_projects_org_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.public_id"],
            name="fk_projects_owner_user_id",
        ),
        sa.UniqueConstraint("org_id", "public_id", name="uq_projects_org_public_id"),
    )
    op.create_index("ix_projects_org_id", "projects", ["org_id"])
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])

    op.create_table(
        "project_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("session_public_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_sessions_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "project_id",
            "session_public_id",
            name="uq_project_sessions_project_session",
        ),
    )
    op.create_index("ix_project_sessions_project_id", "project_sessions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_sessions_project_id", table_name="project_sessions")
    op.drop_table("project_sessions")
    op.drop_index("ix_projects_owner_user_id", table_name="projects")
    op.drop_index("ix_projects_org_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_org_members_user_id", table_name="org_members")
    op.drop_index("ix_org_members_org_id", table_name="org_members")
    op.drop_table("org_members")
    op.drop_index("ix_organizations_owner_user_id", table_name="organizations")
    op.drop_table("organizations")
