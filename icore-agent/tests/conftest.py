from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Use an in-memory SQLite database for account integration tests unless overridden.
os.environ.setdefault("ICORE_TEST_SYNC_DATABASE_URL",
                      "sqlite+pysqlite:///:memory:")


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def use_in_memory_agent_runtime(monkeypatch):
    """Keep HTTP tests from reaching external Redis runtime coordination."""
    dependencies = sys.modules.get(
        "icore_agent.interfaces.http.v1.dependencies")
    if dependencies is None:
        return
    from icore_agent.contexts.agent.application.runtime import (
        AgentRuntime,
        InMemoryAgentRunStore,
    )

    monkeypatch.setattr(
        dependencies,
        "agent_runtime",
        AgentRuntime(run_store=InMemoryAgentRunStore()),
    )
