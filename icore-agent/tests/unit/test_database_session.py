from __future__ import annotations

from unittest.mock import patch


def test_database_session_is_lazy():
    with patch("sqlalchemy.ext.asyncio.create_async_engine") as mock_create_engine:
        import importlib

        module = importlib.import_module("icore_agent.database.session")
        importlib.reload(module)

        assert mock_create_engine.call_count == 0
        module.get_engine()
        assert mock_create_engine.call_count == 1
