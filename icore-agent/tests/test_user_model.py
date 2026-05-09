from __future__ import annotations

from icore_agent.database.models import Base
from icore_agent.users.models import User


def test_user_model_declares_users_table():
    table = User.__table__

    assert table.name == "users"
    assert table is Base.metadata.tables["users"]
    assert set(table.columns.keys()) == {"id", "user_name", "password_hash"}
    assert table.c.id.primary_key is True
    assert table.c.user_name.nullable is False
    assert table.c.user_name.unique is True
    assert table.c.password_hash.nullable is False
