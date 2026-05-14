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
        "ports",
        "minio",
        "kafka",
        "storage",
        "logging",
    }
    for domain in domains:
        assert (dotenv_dir / f".env.{domain}").is_file()
        assert (dotenv_dir / f".env.{domain}.example").is_file()


def test_gitignore_ignores_real_domain_envs_but_allows_examples():
    text = (AGENT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "dotenv/.env.*" in text
    assert "!dotenv/.env.*.example" in text


def test_compose_wrapper_loads_split_env_files():
    root_wrapper = (AGENT_ROOT / "compose.sh").read_text(encoding="utf-8")
    assert 'exec "$SCRIPT_DIR/scripts/compose.sh" "$@"' in root_wrapper

    wrapper = AGENT_ROOT / "scripts" / "compose.sh"
    text = wrapper.read_text(encoding="utf-8")
    assert "docker compose" in text
    for domain in (
        "app",
        "ports",
        "database",
        "memory",
        "minio",
        "kafka",
        "storage",
        "logging",
        "llm",
        "sequential",
        "auth",
        "rag",
        "tools",
        "media",
    ):
        assert f'dotenv/.env.{domain}"' in text

    for compose_file in (
        "base.yml",
        "postgres.yml",
        "redis.yml",
        "minio.yml",
        "kafka.yml",
        "storage-service.yml",
        "logging-service.yml",
        "backend.yml",
    ):
        assert f"infrastructure/docker/compose/{compose_file}" in text


def test_app_env_documents_build_proxy_overrides():
    app_example = (AGENT_ROOT / "dotenv" / ".env.app.example").read_text(
        encoding="utf-8"
    )

    assert "BUILD_HTTP_PROXY=http://host.docker.internal:7890" in app_example
    assert "BUILD_GOPROXY=https://goproxy.cn,direct" in app_example


def test_compose_files_are_split_under_infrastructure():
    compose_dir = AGENT_ROOT / "infrastructure" / "docker" / "compose"
    expected = {
        "base.yml",
        "backend.yml",
        "postgres.yml",
        "redis.yml",
        "minio.yml",
        "kafka.yml",
        "storage-service.yml",
        "logging-service.yml",
    }

    assert compose_dir.is_dir()
    assert expected <= {path.name for path in compose_dir.iterdir()}
    assert not (AGENT_ROOT / "docker-compose.yml").exists()


def test_infrastructure_compose_base_declares_shared_resources():
    base = (
        AGENT_ROOT / "infrastructure" / "docker" / "compose" / "base.yml"
    ).read_text(encoding="utf-8")

    assert "name: icore-agent" in base
    assert "icore-net:" in base
    assert "icore_db:" in base
    assert "redis-data:" in base
    assert "minio-data:" in base
    assert "kafka-data:" in base
    assert "logging-service-data:" in base


def test_postgres_port_mapping_uses_split_database_ports():
    compose = (
        AGENT_ROOT / "infrastructure" / "docker" / "compose" / "postgres.yml"
    ).read_text(encoding="utf-8")
    database_example = (AGENT_ROOT / "dotenv" / ".env.database.example").read_text(
        encoding="utf-8"
    )

    assert "${DB_HOST_PORT:-5432}:${DB_INTERNAL_PORT:-5432}" in compose
    assert "DB_INTERNAL_PORT=5432" in database_example
    assert "DB_HOST_PORT=5432" in database_example
    assert "DB_PORT=" not in database_example


def test_object_and_logging_infra_have_init_services():
    compose_dir = AGENT_ROOT / "infrastructure" / "docker" / "compose"
    minio = (compose_dir / "minio.yml").read_text(encoding="utf-8")
    kafka = (compose_dir / "kafka.yml").read_text(encoding="utf-8")

    assert "minio-init:" in minio
    assert "mc mb --ignore-existing local/icore-agent-images" in minio
    assert "mc mb --ignore-existing local/icore-agent-attachments" in minio

    assert "kafka-init:" in kafka
    assert "--if-not-exists" in kafka
    assert 'topic "$$LOGGING_KAFKA_TOPIC"' in kafka


def test_go_microservice_dockerfiles_use_buildkit_caches():
    services_dir = AGENT_ROOT / "src" / "icore_agent" / "services"

    for service_name in ("storage-service", "logging-service"):
        dockerfile = (services_dir / service_name / "Dockerfile").read_text(
            encoding="utf-8"
        )

        assert "--mount=type=cache,target=/go/pkg/mod" in dockerfile
        assert "--mount=type=cache,target=/root/.cache/go-build" in dockerfile


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


def test_copied_logging_client_does_not_reference_old_project_packages():
    logger = (AGENT_ROOT / "src" / "icore_agent" / "lib" / "logging" / "logger.py").read_text(
        encoding="utf-8"
    )

    assert "from lib.logging" not in logger
    assert "app.core.system.request_context" not in logger
    assert "medical_backend" not in logger


def test_fastapi_app_installs_request_id_middleware():
    main = (AGENT_ROOT / "src" / "icore_agent" / "main.py").read_text(encoding="utf-8")

    assert "from .lib.http.middleware import RequestIdMiddleware" in main
    assert "app.add_middleware(RequestIdMiddleware)" in main


def test_email_validator_dependency_is_declared_for_emailstr_models():
    pyproject = (AGENT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (AGENT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert '"email-validator' in pyproject
    assert "email-validator==" in requirements


def test_dockerignore_excludes_local_runtime_artifacts_and_real_envs():
    dockerignore = (AGENT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".venv/" in dockerignore
    assert "__pycache__/" in dockerignore
    assert "dotenv/.env.*" in dockerignore
    assert "!dotenv/.env.*.example" in dockerignore
