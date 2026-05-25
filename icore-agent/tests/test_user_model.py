from __future__ import annotations

from typing import Any, cast

from icore_agent.domain.user import AuthenticatedUser, UserProfile
from icore_agent.infrastructure.persistence.sqlalchemy.models import Base
from icore_agent.infrastructure.persistence.users.models import User


def test_user_model_declares_account_columns():
    table = cast(Any, User.__table__)

    assert table.name == "users"
    assert table is Base.metadata.tables["users"]
    expected = {
        "id",
        "public_id",
        "user_name",
        "password_hash",
        "email",
        "name",
        "plan",
        "plan_label",
        "organization_id",
        "organization_name",
        "roles",
        "byok",
        "usage",
        "created_at",
        "updated_at",
    }
    assert set(table.columns.keys()) == expected
    assert table.c.public_id.unique is True
    assert table.c.email.unique is True


def test_authenticated_user_is_built_from_user_profile() -> None:
    """Authenticated requests should carry a domain user context, not a dict."""
    profile = UserProfile(
        public_id="user-1",
        email="user@example.com",
        name="User One",
        plan="free",
        plan_label="Free",
        organization_id="org-1",
        organization_name="Org One",
        roles=["owner", "admin"],
        byok={"enabled": True, "model": "openai/gpt-4o-mini"},
        usage={"messages": 3},
        created_at=10,
        updated_at=20,
    )

    user = AuthenticatedUser.from_profile(profile)

    assert user.public_id == "user-1"
    assert user.roles == ("owner", "admin")
    assert user.byok["model"] == "openai/gpt-4o-mini"
    assert user.usage["messages"] == 3
