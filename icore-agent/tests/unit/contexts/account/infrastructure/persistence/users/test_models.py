from __future__ import annotations

from typing import Any, cast

from icore_agent.contexts.account.infrastructure.persistence.users.models import User
from icore_agent.infrastructure.persistence.sqlalchemy.models import Base


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
