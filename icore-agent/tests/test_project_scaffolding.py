from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = PROJECT_ROOT / "icore-agent"


def test_alembic_scaffold_is_in_backend_root():
    assert (AGENT_ROOT / "alembic.ini").is_file()
    assert (AGENT_ROOT / "alembic" / "env.py").is_file()
    versions = AGENT_ROOT / "alembic" / "versions"
    assert versions.is_dir()
    assert any(path.name.startswith("0001") and "users" in path.name for path in versions.iterdir())


def test_root_agents_md_documents_repo_workflow():
    text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "DDD" in text
    assert "Alembic" in text
    assert "测试" in text
    assert "git" in text
