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


def test_dotenv_files_are_split_by_domain():
    assert not (AGENT_ROOT / ".env.example").exists()
    dotenv_dir = AGENT_ROOT / "dotenv"
    domains = {
        "app",
        "database",
        "llm",
        "sequential",
        "memory",
        "auth",
        "rag",
        "tools",
        "media",
    }
    for domain in domains:
        assert (dotenv_dir / f".env.{domain}").is_file()
        assert (dotenv_dir / f".env.{domain}.example").is_file()


def test_gitignore_ignores_real_domain_envs_but_allows_examples():
    text = (AGENT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "dotenv/.env.*" in text
    assert "!dotenv/.env.*.example" in text


def test_compose_wrapper_loads_split_env_files():
    wrapper = AGENT_ROOT / "compose.sh"
    text = wrapper.read_text(encoding="utf-8")
    assert "docker compose" in text
    for domain in ("app", "database", "llm", "sequential", "memory", "auth", "rag", "tools", "media"):
        assert f"--env-file dotenv/.env.{domain}" in text


def test_postgres_port_mapping_uses_split_database_ports():
    compose = (AGENT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    database_example = (AGENT_ROOT / "dotenv" / ".env.database.example").read_text(
        encoding="utf-8"
    )

    assert "${DB_HOST_PORT:-5432}:${DB_INTERNAL_PORT:-5432}" in compose
    assert "DB_INTERNAL_PORT=5432" in database_example
    assert "DB_HOST_PORT=5432" in database_example
    assert "DB_PORT=" not in database_example


def test_dockerfile_keeps_dependency_layer_before_source_copy():
    dockerfile = (AGENT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    metadata_copy = dockerfile.index("COPY pyproject.toml")
    dependency_install = dockerfile.index("requirements-runtime.txt")
    source_copy = dockerfile.index("COPY src/")

    assert metadata_copy < dependency_install < source_copy
    assert "--prefix=/install/deps" in dockerfile
    assert "--prefix=/install/app" in dockerfile
    assert "COPY --from=builder /install/deps /usr/local" in dockerfile
    assert "COPY --from=builder /install/app /usr/local" in dockerfile
    assert "--no-deps dist/*.whl" in dockerfile


def test_dockerignore_excludes_local_runtime_artifacts_and_real_envs():
    dockerignore = (AGENT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".venv/" in dockerignore
    assert "__pycache__/" in dockerignore
    assert "dotenv/.env.*" in dockerignore
    assert "!dotenv/.env.*.example" in dockerignore
