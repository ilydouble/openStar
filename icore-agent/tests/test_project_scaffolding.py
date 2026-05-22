from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = PROJECT_ROOT / "icore-agent"


def test_alembic_scaffold_is_in_backend_root():
    assert (AGENT_ROOT / "alembic.ini").is_file()
    assert (AGENT_ROOT / "alembic" / "env.py").is_file()
    versions = AGENT_ROOT / "alembic" / "versions"
    assert versions.is_dir()
    assert any(path.name.startswith("0001")
               and "users" in path.name for path in versions.iterdir())


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
        "minio",
        "kafka",
        "storage",
        "logging",
        "clickhouse",
        "gateway",
        "build",
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
        "build",
        "database",
        "memory",
        "minio",
        "kafka",
        "storage",
        "logging",
        "clickhouse",
        "gateway",
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
        "click-house.yml",
        "backend.yml",
        "gateway.yml",
    ):
        assert f"infrastructure/docker/compose/{compose_file}" in text


def test_app_env_documents_build_proxy_overrides():
    build_example = (AGENT_ROOT / "dotenv" / ".env.build.example").read_text(
        encoding="utf-8"
    )

    assert "BUILD_HTTP_PROXY=" in build_example
    assert "BUILD_GOPROXY=https://goproxy.cn,direct" in build_example


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
        "click-house.yml",
        "gateway.yml",
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
    assert "clickhouse-data:" in base


def test_clickhouse_logging_infra_is_declared():
    compose_dir = AGENT_ROOT / "infrastructure" / "docker" / "compose"
    clickhouse = (compose_dir / "click-house.yml").read_text(encoding="utf-8")
    clickhouse_example = (AGENT_ROOT / "dotenv" / ".env.clickhouse.example").read_text(
        encoding="utf-8"
    )
    logging_example = (AGENT_ROOT / "dotenv" / ".env.logging.example").read_text(
        encoding="utf-8"
    )
    migrations_dir = AGENT_ROOT / "infrastructure" / "clickhouse" / "migrations"

    assert "clickhouse/clickhouse-server" in clickhouse
    assert "clickhouse-migrate:" in clickhouse
    assert "clickhouse-writer:" in clickhouse
    assert "CLICKHOUSE_DATABASE=icore_logging_db" in clickhouse_example
    assert "CLICKHOUSE_WRITER_GROUP_ID=logging-clickhouse-writer" in clickhouse_example
    assert "kafka_invalid_temp_events.jsonl" in logging_example
    assert "kafka_invalid_temp_error_audit_events.jsonl" in logging_example
    assert (
        AGENT_ROOT / "infrastructure" / "clickhouse" / "bootstrap.sh"
    ).is_file()
    assert (migrations_dir / "000001_create_icore_logs.up.sql").is_file()
    assert (migrations_dir / "000001_create_icore_logs.down.sql").is_file()


def test_postgres_port_mapping_uses_split_database_ports():
    compose = (
        AGENT_ROOT / "infrastructure" / "docker" / "compose" / "postgres.yml"
    ).read_text(encoding="utf-8")
    database_example = (AGENT_ROOT / "dotenv" / ".env.database.example").read_text(
        encoding="utf-8"
    )

    assert (
        "${DB_HOST_BIND:-127.0.0.1}:${DB_HOST_PORT:-15432}:${DB_INTERNAL_PORT:-5432}"
        in compose
    )
    assert "DB_INTERNAL_PORT=5432" in database_example
    assert "DB_HOST_BIND=127.0.0.1" in database_example
    assert "DB_HOST_PORT=15432" in database_example
    assert "DB_PORT=" not in database_example


def test_object_and_logging_infra_have_init_services():
    compose_dir = AGENT_ROOT / "infrastructure" / "docker" / "compose"
    minio = (compose_dir / "minio.yml").read_text(encoding="utf-8")
    kafka = (compose_dir / "kafka.yml").read_text(encoding="utf-8")

    assert "minio-init:" in minio
    assert "mc mb --ignore-existing local/icore-agent-images" in minio
    assert "mc mb --ignore-existing local/icore-files" in minio

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


def test_go_modules_use_icore_names():
    services_dir = AGENT_ROOT / "src" / "icore_agent" / "services"
    stale_markers = (
        "xiehe-services-lib-go",
        "xiehe-gateway",
        "xiehe-logging-service",
        "xiehe-storage-service",
    )
    scanned_paths = [
        path
        for pattern in ("*.go", "go.mod", "go.work")
        for path in services_dir.rglob(pattern)
    ]
    stale_paths = [
        str(path.relative_to(services_dir))
        for path in scanned_paths
        if any(marker in path.read_text(encoding="utf-8") for marker in stale_markers)
    ]

    lib_go_mod = (services_dir / "lib-go" /
                  "go.mod").read_text(encoding="utf-8")
    assert "module icore-services-lib-go" in lib_go_mod
    assert stale_paths == []


def test_gateway_ddd_layers_keep_http_policy_and_infrastructure_split():
    """Verify gateway HTTP adapters stay thin and DDD layer boundaries remain explicit."""
    services_dir = AGENT_ROOT / "src" / "icore_agent" / "services"
    gateway_internal = services_dir / "gateway" / "internal"
    domain_dir = gateway_internal / "domain"
    application_dir = gateway_internal / "application"
    interfaces_dir = gateway_internal / "interfaces" / "http"
    infrastructure_dir = gateway_internal / "infrastructure"
    lib_logging_dir = services_dir / "lib-go" / "logging"

    assert (domain_dir / "identity" / "identity.go").is_file()
    assert (domain_dir / "auth" / "auth_decision.go").is_file()
    assert (domain_dir / "rate_limit" / "rate_limit_decision.go").is_file()
    assert (domain_dir / "logging" / "access_log.go").is_file()
    assert (domain_dir / "request_id" / "request_id.go").is_file()

    assert (application_dir / "pipeline" / "pipeline.go").is_file()
    assert (application_dir / "route_policy" / "route_policy.go").is_file()
    assert (application_dir / "identity_policy" /
            "identity_policy.go").is_file()

    assert (interfaces_dir / "router.go").is_file()
    assert (interfaces_dir / "router_test.go").is_file()
    assert (interfaces_dir / "handler.go").is_file()
    assert (interfaces_dir / "response_status_recorder.go").is_file()

    assert (infrastructure_dir / "jwt" / "authenticator.go").is_file()
    assert (infrastructure_dir / "rate_limiter" /
            "redis_limiter.go").is_file()
    assert (infrastructure_dir / "logging" /
            "gateway_access_logger.go").is_file()
    assert (infrastructure_dir / "proxy" / "reverse_proxy.go").is_file()

    old_gateway_dir = gateway_internal / "gateway"
    assert not list(old_gateway_dir.rglob("*.go"))

    handler_text = (interfaces_dir / "handler.go").read_text(
        encoding="utf-8")
    for forbidden in (
        "Authenticate(",
        "RateLimit",
        "ReverseProxy",
        "httputil",
        "LoggingServiceClient",
    ):
        assert forbidden not in handler_text

    assert (lib_logging_dir / "logging_service_client.go").is_file()
    assert (lib_logging_dir / "app_logger.go").is_file()


def test_gateway_rate_limit_env_uses_token_bucket_profiles():
    """Keep gateway env examples and compose on token bucket rate/burst knobs."""
    gateway_env = (AGENT_ROOT / "dotenv" /
                   ".env.gateway.example").read_text(encoding="utf-8")
    gateway_compose = (
        AGENT_ROOT / "infrastructure" / "docker" /
        "compose" / "gateway.yml"
    ).read_text(encoding="utf-8")

    required = {
        "GATEWAY_RATE_LIMIT_KEY_PREFIX",
        "GATEWAY_CLIENT_IP_RATE",
        "GATEWAY_CLIENT_IP_BURST",
        "GATEWAY_USER_ID_RATE",
        "GATEWAY_USER_ID_BURST",
        "ICORE_AGENT_RATE",
        "ICORE_AGENT_BURST",
    }
    forbidden = {
        "GATEWAY_RATE_LIMIT_WINDOW",
        "GATEWAY_RATE_LIMIT_WINDOW_LIMIT",
    }
    for name in required:
        assert name in gateway_env
        assert name in gateway_compose
    for name in forbidden:
        assert name not in gateway_env
        assert name not in gateway_compose


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
    client = (AGENT_ROOT / "src" / "icore_agent" / "shared" /
              "logging" / "logging_service_client.py").read_text(
        encoding="utf-8"
    )

    assert "from lib.logging" not in client
    assert "app.core.system.request_context" not in client
    assert "medical_backend" not in client


def test_logging_facade_uses_clear_layered_names():
    logging_dir = AGENT_ROOT / "src" / "icore_agent" / "shared" / "logging"

    assert (logging_dir / "logging_service_client.py").exists()
    assert (logging_dir / "app_logger.py").exists()
    assert not (logging_dir / "logger.py").exists()
    assert not (logging_dir / "service_logger.py").exists()


def test_fastapi_app_installs_request_id_middleware():
    main = (AGENT_ROOT / "src" / "icore_agent" /
            "main.py").read_text(encoding="utf-8")

    assert "RequestIdMiddleware" in main
    assert "app.add_middleware(RequestIdMiddleware)" in main
    assert "BackendRequestLoggingMiddleware" in main
    assert "app.add_middleware(BackendRequestLoggingMiddleware)" in main


def test_backend_no_longer_depends_on_legacy_structured_logger():
    """Verify backend logs go through the internal logging-service facade."""
    pyproject = (AGENT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (
        AGENT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    legacy_package = "struct" + "log"

    assert legacy_package not in pyproject
    assert legacy_package not in requirements


def test_email_validator_dependency_is_declared_for_emailstr_models():
    pyproject = (AGENT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (
        AGENT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert '"email-validator' in pyproject
    assert "email-validator==" in requirements


def test_python_backend_uses_clean_architecture_layers():
    """Keep Python backend code grouped by abstraction layer, not mixed top-level folders."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"

    expected_layers = {
        "application",
        "config",
        "domain",
        "engine",
        "infrastructure",
        "interfaces",
        "services",
        "shared",
        "tools",
    }
    assert expected_layers <= {
        path.name for path in package_dir.iterdir() if path.is_dir()
    }

    mixed_top_level_dirs = {
        "api",
        "control_plane",
        "database",
        "lib",
        "memory",
        "users",
    }
    assert not (mixed_top_level_dirs & {
        path.name for path in package_dir.iterdir() if path.is_dir()
    })


def test_http_interface_layer_is_split_by_business_domain():
    """Keep HTTP adapters grouped by domain with fine-grained schemas and handlers."""
    http_dir = AGENT_ROOT / "src" / "icore_agent" / "interfaces" / "http"
    v1_dir = http_dir / "v1"

    assert (v1_dir / "router.py").is_file()

    expected_domains = {
        "account": {
            "schemas": {"auth.py", "billing.py", "lead.py", "project.py", "team.py"},
            "handlers": {"auth.py", "billing.py", "lead.py", "profile.py", "project.py", "team.py"},
        },
        "agent": {
            "schemas": {"chat.py", "sequential.py", "transcribe.py"},
            "handlers": {"chat.py", "sequential.py", "session.py", "transcribe.py"},
        },
        "files": {
            "schemas": {"files.py"},
            "handlers": {"files.py"},
        },
        "health": {
            "schemas": {"probe.py"},
            "handlers": {"probe.py"},
        },
        "knowledge": {
            "schemas": {"document.py"},
            "handlers": {"documents.py"},
        },
        "payment": {
            "schemas": {"checkout.py", "order.py", "upgrade.py"},
            "handlers": {"checkout.py", "order.py", "upgrade.py", "webhook.py"},
        },
    }
    for domain, expected in expected_domains.items():
        assert not (http_dir / domain).exists()
        domain_dir = v1_dir / domain
        assert (domain_dir / "router.py").is_file()
        for layer, filenames in expected.items():
            layer_dir = domain_dir / layer
            assert (layer_dir / "__init__.py").is_file()
            assert filenames <= {path.name for path in layer_dir.glob("*.py")}
    assert (v1_dir / "users" / "serializers.py").is_file()


def test_agent_chat_handler_stays_http_adapter_only():
    """Keep chat application orchestration and SSE framing out of the handler."""
    handler = (
        AGENT_ROOT
        / "src"
        / "icore_agent"
        / "interfaces"
        / "http"
        / "v1"
        / "agent"
        / "handlers"
        / "chat.py"
    ).read_text(encoding="utf-8")

    forbidden_fragments = {
        "import pandas",
        "import threading",
        "import json",
        "create_orchestrator",
        "infrastructure.memory",
        "set_runtime_user",
        "set_parent_callback",
        "data: [DONE]",
        "text/event-stream",
    }
    for fragment in forbidden_fragments:
        assert fragment not in handler


def test_fastapi_app_uses_http_interface_router_composition_entrypoint():
    """Keep application startup decoupled from individual business-domain routers."""
    main = (AGENT_ROOT / "src" / "icore_agent" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "from .interfaces.http.v1.router import include_api_routers" in main
    assert "include_api_routers(app)" in main
    assert "from .api" not in main


def test_domain_infrastructure_and_shared_layers_own_lower_level_concepts():
    """Keep domain rules, infrastructure adapters, and shared helpers separated."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"

    assert (package_dir / "domain" / "account" / "plans.py").is_file()
    assert (package_dir / "domain" / "user" / "user_repository.py").is_file()
    assert (package_dir / "domain" / "user" / "models.py").is_file()
    assert (
        package_dir / "infrastructure" / "persistence" / "users" /
        "sqlalchemy_repository.py"
    ).is_file()
    assert (package_dir / "shared" / "runtime" / "user_context.py").is_file()
    assert (package_dir / "shared" / "auth" / "jwt.py").is_file()
    assert (package_dir / "shared" / "logging" / "app_logger.py").is_file()
    assert (
        package_dir / "infrastructure" /
        "persistence" / "sqlalchemy" / "sync_session.py"
    ).is_file()
    assert not (
        package_dir / "infrastructure" / "persistence" / "users" / "repository.py"
    ).exists()
    assert (
        package_dir / "infrastructure" / "control_plane" / "json_store.py"
    ).is_file()
    assert (
        package_dir / "infrastructure" / "memory" / "conversation.py"
    ).is_file()


def test_domain_user_repository_is_abstract_not_sqlalchemy_bound():
    """Keep the domain repository free of concrete persistence and API serialization."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"
    repository = (
        package_dir / "domain" / "user" / "user_repository.py"
    ).read_text(encoding="utf-8")

    assert "Protocol" in repository
    assert "sqlalchemy" not in repository.lower()
    assert "Session" not in repository
    assert "select(" not in repository
    assert "infrastructure.persistence.users.models" not in repository
    assert "user_to_api_dict" not in repository


def test_http_v1_owns_user_serialization():
    """Keep user HTTP payload formatting out of domain and persistence layers."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"
    serializer = (
        package_dir / "interfaces" / "http" / "v1" /
        "users" / "serializers.py"
    ).read_text(encoding="utf-8")
    persistence_dir = package_dir / "infrastructure" / "persistence" / "users"

    assert "serialize_user_profile" in serializer
    assert "UserProfile" in serializer
    assert not (persistence_dir / "mappers.py").exists()


def test_usage_policy_and_user_import_live_in_application_layer():
    """Keep quota rules and legacy import mapping out of repositories."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"
    usage_policy = package_dir / "application" / "usage" / "policy.py"
    user_import = package_dir / "application" / "user_import" / "service.py"
    postgres_repositories = (
        package_dir / "infrastructure" / "persistence" /
        "users" / "postgres_repositories.py"
    ).read_text(encoding="utf-8")
    json_import = (
        package_dir / "infrastructure" / "persistence" /
        "users" / "json_import.py"
    ).read_text(encoding="utf-8")

    assert usage_policy.is_file()
    assert user_import.is_file()
    assert "def check_quota" not in postgres_repositories
    assert "def consume_quota" not in postgres_repositories
    assert "LegacyUserImportService" in json_import
    assert "upsert_from_legacy_dict" not in json_import


def test_dockerignore_excludes_local_runtime_artifacts_and_real_envs():
    dockerignore = (AGENT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".venv/" in dockerignore
    assert "__pycache__/" in dockerignore
    assert "dotenv/.env.*" in dockerignore
    assert "!dotenv/.env.*.example" in dockerignore
