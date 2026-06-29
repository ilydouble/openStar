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
        "agent",
        "database",
        "llm",
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
    for mode in ("dev", "production"):
        mode_dir = dotenv_dir / mode
        assert mode_dir.is_dir()
        for domain in domains:
            assert (mode_dir / f".env.{domain}.example").is_file()

    dev_examples = {
        path.name: path.read_text(encoding="utf-8")
        for path in (dotenv_dir / "dev").glob(".env.*.example")
    }
    production_examples = {
        path.name: path.read_text(encoding="utf-8")
        for path in (dotenv_dir / "production").glob(".env.*.example")
    }
    assert dev_examples == production_examples
    assert not (dotenv_dir / ".env.sequential.example").exists()
    assert not list(dotenv_dir.glob(".env.*.example"))


def test_gitignore_ignores_real_domain_envs_but_allows_examples():
    text = (AGENT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "dotenv/**/.env.*" in text
    assert "!dotenv/**/.env.*.example" in text


def test_compose_wrapper_loads_split_env_files():
    root_wrapper = (AGENT_ROOT / "compose.sh").read_text(encoding="utf-8")
    assert 'exec "$SCRIPT_DIR/scripts/compose.sh" "$@"' in root_wrapper

    wrapper = AGENT_ROOT / "scripts" / "compose.sh"
    text = wrapper.read_text(encoding="utf-8")
    assert "docker compose" in text
    assert '"${1:-}" == "dev"' in text
    assert '"${1:-}" == "production"' in text
    assert 'BUILD_ENV_FILE="$PROJECT_DIR/dotenv/$MODE/.env.build"' in text
    assert 'ICORE_COMPOSE_DOTENV_DIR="$PROJECT_DIR/dotenv/$MODE"' in text
    assert 'ICORE_COMPOSE_ENV_SUFFIX=".example"' in text
    for domain in (
        "app",
        "agent",
        "build",
        "database",
        "payment",
        "memory",
        "minio",
        "kafka",
        "storage",
        "logging",
        "clickhouse",
        "gateway",
        "llm",
        "auth",
        "rag",
        "tools",
        "media",
    ):
        assert f'"dotenv/$MODE/.env.{domain}"' in text
    assert 'dotenv/.env.sequential"' not in text

    for compose_file in (
        "base.yml",
        "postgres.yml",
        "payment-service.yml",
        "redis.yml",
        "minio.yml",
        "kafka.yml",
        "storage-service.yml",
        "logging-service.yml",
        "click-house.yml",
        "backend.yml",
        "gateway.yml",
    ):
        assert f"infrastructure/docker/compose/dev/{compose_file}" in text
    for compose_file in (
        "base.yml",
        "minio.yml",
        "kafka.yml",
        "click-house.yml",
        "storage-service.yml",
        "logging-service.yml",
        "payment-service.yml",
        "backend.yml",
        "gateway.yml",
    ):
        assert f"infrastructure/docker/compose/production/{compose_file}" in text


def test_app_env_documents_build_proxy_overrides():
    for mode in ("dev", "production"):
        build_example = (
            AGENT_ROOT / "dotenv" / mode / ".env.build.example"
        ).read_text(encoding="utf-8")

        assert "BUILD_HTTP_PROXY=" in build_example
        assert "BUILD_GOPROXY=https://goproxy.cn,direct" in build_example


def test_tools_env_documents_agent_tool_workspace():
    """Tool workspace configuration should live in the tools dotenv domain."""
    for mode in ("dev", "production"):
        tools_example = (
            AGENT_ROOT / "dotenv" / mode / ".env.tools.example"
        ).read_text(encoding="utf-8")

        assert "AGENT_TOOL_WORKSPACE=/tmp/icore-agent-workspace" in tools_example


def test_compose_files_are_split_under_infrastructure():
    compose_dir = AGENT_ROOT / "infrastructure" / "docker" / "compose"
    dev_expected = {
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
    production_expected = {
        "base.yml",
        "backend.yml",
        "minio.yml",
        "kafka.yml",
        "click-house.yml",
        "storage-service.yml",
        "logging-service.yml",
        "payment-service.yml",
        "gateway.yml",
    }

    assert compose_dir.is_dir()
    assert {"dev", "production"} <= {
        path.name for path in compose_dir.iterdir() if path.is_dir()
    }
    assert dev_expected <= {path.name for path in (
        compose_dir / "dev").iterdir()}
    assert production_expected <= {
        path.name for path in (compose_dir / "production").iterdir()
    }
    assert not [path for path in compose_dir.iterdir() if path.is_file()]
    assert not (AGENT_ROOT / "docker-compose.yml").exists()

    for mode in ("dev", "production"):
        for compose_file in (compose_dir / mode).iterdir():
            if compose_file.suffix not in {".yml", ".yaml"}:
                continue
            compose_text = compose_file.read_text(encoding="utf-8")
            assert "../../../../dotenv/dev" not in compose_text
            assert "../../../../dotenv/production" not in compose_text


def test_infrastructure_compose_base_declares_shared_resources():
    dev_base = (
        AGENT_ROOT / "infrastructure" / "docker" / "compose" / "dev" / "base.yml"
    ).read_text(encoding="utf-8")
    production_base = (
        AGENT_ROOT
        / "infrastructure"
        / "docker"
        / "compose"
        / "production"
        / "base.yml"
    ).read_text(encoding="utf-8")

    assert "name: icore-agent" in dev_base
    assert "icore-net:" in dev_base
    assert "icore_db:" in dev_base
    assert "redis-data:" in dev_base
    assert "minio-data:" in dev_base
    assert "kafka-data:" in dev_base
    assert "logging-service-data:" in dev_base
    assert "clickhouse-data:" in dev_base

    assert "name: icore-agent" in production_base
    assert "networks:" not in production_base
    assert "logging-service-data:" in production_base


def test_production_compose_uses_host_network_without_infra_services():
    """Production starts app and init services, but not infrastructure daemons."""
    compose_dir = AGENT_ROOT / "infrastructure" / "docker" / "compose" / "production"
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(compose_dir.glob("*.yml"))
    )

    for service_name in (
        "icore-agent:",
        "gateway:",
        "storage-service:",
        "logging-service:",
        "clickhouse-writer:",
        "payment-service:",
        "payment-events-consumer:",
        "minio-init:",
        "kafka-init:",
        "clickhouse-migrate:",
        "payment-db-migrate:",
    ):
        assert f"\n  {service_name}" in combined

    for service_name in (
        "postgres:",
        "redis:",
        "minio:",
        "kafka:",
        "clickhouse:",
    ):
        assert f"\n  {service_name}" not in combined

    assert "networks:" not in combined
    assert "network_mode: host" in combined
    assert "127.0.0.1" in combined


def test_clickhouse_logging_infra_is_declared():
    compose_dir = AGENT_ROOT / "infrastructure" / "docker" / "compose"
    dev_clickhouse = (compose_dir / "dev" / "click-house.yml").read_text(
        encoding="utf-8"
    )
    production_clickhouse = (
        compose_dir / "production" / "click-house.yml"
    ).read_text(encoding="utf-8")
    clickhouse_example = (
        AGENT_ROOT / "dotenv" / "dev" / ".env.clickhouse.example"
    ).read_text(encoding="utf-8")
    logging_example = (
        AGENT_ROOT / "dotenv" / "dev" / ".env.logging.example"
    ).read_text(encoding="utf-8")
    migrations_dir = AGENT_ROOT / "infrastructure" / "clickhouse" / "migrations"

    assert "clickhouse/clickhouse-server" in dev_clickhouse
    assert "clickhouse-migrate:" in dev_clickhouse
    assert "clickhouse-writer:" in dev_clickhouse
    assert "clickhouse/clickhouse-server" not in production_clickhouse
    assert "clickhouse-migrate:" in production_clickhouse
    assert "clickhouse-writer:" in production_clickhouse
    assert "network_mode: host" in production_clickhouse
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
        AGENT_ROOT / "infrastructure" / "docker" / "compose" / "dev" / "postgres.yml"
    ).read_text(encoding="utf-8")
    database_example = (
        AGENT_ROOT / "dotenv" / "dev" / ".env.database.example"
    ).read_text(encoding="utf-8")

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
    dev_minio = (compose_dir / "dev" / "minio.yml").read_text(encoding="utf-8")
    dev_kafka = (compose_dir / "dev" / "kafka.yml").read_text(encoding="utf-8")
    production_minio = (
        compose_dir / "production" / "minio.yml"
    ).read_text(encoding="utf-8")
    production_kafka = (
        compose_dir / "production" / "kafka.yml"
    ).read_text(encoding="utf-8")

    assert "minio:" in dev_minio
    assert "minio-init:" in dev_minio
    assert "mc mb --ignore-existing local/icore-agent-images" in dev_minio
    assert "mc mb --ignore-existing local/icore-files" in dev_minio
    assert "minio:" not in production_minio
    assert "minio-init:" in production_minio
    assert "network_mode: host" in production_minio

    assert "kafka:" in dev_kafka
    assert "kafka-init:" in dev_kafka
    assert "--if-not-exists" in dev_kafka
    assert 'topic "$$LOGGING_KAFKA_TOPIC"' in dev_kafka
    assert "PAYMENT_KAFKA_TOPIC" in dev_kafka
    assert "PAYMENT_KAFKA_PARTITIONS" in dev_kafka
    assert 'topic "$$PAYMENT_KAFKA_TOPIC"' in dev_kafka
    assert "\n  kafka:" not in production_kafka
    assert "kafka-init:" in production_kafka
    assert "network_mode: host" in production_kafka


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
    gateway_env = (
        AGENT_ROOT / "dotenv" / "dev" / ".env.gateway.example"
    ).read_text(encoding="utf-8")
    gateway_compose = (
        AGENT_ROOT
        / "infrastructure"
        / "docker"
        / "compose"
        / "dev"
        / "gateway.yml"
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

    dependency_manifest_copy = dockerfile.index(
        "COPY pyproject.toml requirements.txt"
    )
    dependency_install = dockerfile.index("pip install --prefix=/install/deps")
    source_copy = dockerfile.index("COPY src/")

    assert dependency_manifest_copy < dependency_install < source_copy
    assert "--mount=type=cache,target=/root/.cache/pip" in dockerfile
    assert "--prefix=/install/deps" in dockerfile
    assert "--prefix=/install/app" in dockerfile
    assert "COPY --from=builder /install/deps /usr/local" in dockerfile
    assert "COPY --from=builder /install/app /usr/local" in dockerfile
    assert "--no-deps dist/*.whl" in dockerfile
    assert "tomllib" not in dockerfile
    assert "requirements-runtime.txt" not in dockerfile
    assert "icore-seq-workspace" not in dockerfile
    assert "/tmp/icore-agent-workspace" in dockerfile


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


def test_litellm_and_openai_dependency_pins_are_compatible():
    """Keep Docker's requirements install compatible with LiteLLM's SDK pin."""
    pyproject = (AGENT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (
        AGENT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "litellm==1.83.8" in requirements
    assert "openai==2.24.0" in requirements
    assert '"openai>=2.24.0"' in pyproject


def test_python_backend_uses_clean_architecture_layers():
    """Keep Python backend code grouped by abstraction layer, not mixed top-level folders."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"

    expected_layers = {
        "application",
        "config",
        "domain",
        "infrastructure",
        "interfaces",
        "services",
        "shared",
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
        "engine",
        "tools",
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
            "schemas": {"chat.py", "transcribe.py"},
            "handlers": {"chat.py", "session.py", "transcribe.py"},
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
            "schemas": {"checkout.py", "order.py"},
            "handlers": {"checkout.py", "order.py", "webhook.py"},
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


def test_python_payment_router_does_not_expose_direct_plan_upgrade():
    """Verify paid plans cannot be activated through a public backend route."""
    router = (
        AGENT_ROOT
        / "src"
        / "icore_agent"
        / "interfaces"
        / "http"
        / "v1"
        / "payment"
        / "router.py"
    ).read_text(encoding="utf-8")

    assert "upgrade-plan" not in router
    assert "upgrade_plan" not in router


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
        "data: [DONE]",
        "text/event-stream",
    }
    for fragment in forbidden_fragments:
        assert fragment not in handler


def test_agent_chat_handler_uses_domain_authenticated_user():
    """Keep authenticated user payload dicts out of chat commands."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"
    handler = (
        package_dir / "interfaces" / "http" / "v1" /
        "agent" / "handlers" / "chat.py"
    ).read_text(encoding="utf-8")
    command = (
        package_dir / "domain" / "agent" / "turn" / "turn_command.py"
    ).read_text(encoding="utf-8")
    dependencies = (
        package_dir / "interfaces" / "http" / "v1" / "dependencies.py"
    ).read_text(encoding="utf-8")

    assert "AuthenticatedUser" in handler
    assert "user=dict(user)" not in handler
    assert "user: AuthenticatedUser" in command
    assert "serialize_user_profile(service.get_current_user" not in dependencies


def test_agent_application_uses_explicit_turn_and_session_boundaries():
    """Keep agent turn/session/runtime code under the agent application package."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"
    chat_dir = package_dir / "application" / "chat"
    agent_dir = package_dir / "application" / "agent"
    routing = (agent_dir / "turn" / "routing.py").read_text(encoding="utf-8")
    roles = (package_dir / "domain" / "agent" / "roles.py").read_text(
        encoding="utf-8"
    )
    agent_context_dir = agent_dir / "context"
    agent_domain_loop_dir = package_dir / "domain" / "agent" / "loop"
    agent_domain_context_dir = package_dir / "domain" / "agent" / "context"
    agent_domain_prompt_dir = package_dir / "domain" / "agent" / "prompt"
    agent_domain_turn_dir = package_dir / "domain" / "agent" / "turn"
    agent_prompt_dir = agent_dir / "prompt"
    agent_turn_dir = agent_dir / "turn"
    agent_session_dir = agent_dir / "session"
    agent_runner_dir = agent_dir / "runner"
    agent_tool_dir = agent_dir / "tool"
    legacy_vendor = "str" + "ands"
    legacy_vendor_title = "Str" + "ands"
    legacy_vendor_dir = package_dir / "infrastructure" / "agent" / legacy_vendor
    chat_completions_dir = (
        package_dir / "infrastructure" / "agent" / "chat_completions"
    )
    turn_service = (agent_turn_dir / "service.py").read_text(
        encoding="utf-8"
    )
    session_service = (agent_session_dir / "service.py").read_text(
        encoding="utf-8"
    )
    agent_init = (
        agent_dir / "__init__.py"
    ).read_text(encoding="utf-8")

    chat_sources = list(chat_dir.rglob("*.py")) if chat_dir.exists() else []
    assert chat_sources == []
    assert (agent_context_dir / "__init__.py").is_file()
    assert (agent_context_dir / "loader.py").is_file()
    assert not (agent_context_dir / "models.py").exists()
    assert (agent_domain_context_dir / "__init__.py").is_file()
    assert not (agent_domain_context_dir / "models.py").exists()
    assert (agent_domain_context_dir / "attachments.py").is_file()
    assert (agent_domain_context_dir / "loaded_context.py").is_file()
    assert (agent_domain_prompt_dir / "__init__.py").is_file()
    assert (agent_domain_prompt_dir / "prompt_envelope.py").is_file()
    assert (agent_domain_prompt_dir / "system_prompt.py").is_file()
    assert (agent_domain_loop_dir / "__init__.py").is_file()
    assert (agent_domain_loop_dir / "model_step.py").is_file()
    assert (agent_domain_loop_dir / "model_client.py").is_file()
    assert (agent_domain_loop_dir / "context_manager.py").is_file()
    assert (agent_domain_loop_dir / "tool_runtime.py").is_file()
    assert (agent_domain_loop_dir / "control.py").is_file()
    assert (agent_domain_turn_dir / "turn_command.py").is_file()
    assert not (agent_dir / "commands.py").exists()
    assert (agent_prompt_dir / "__init__.py").is_file()
    assert (agent_prompt_dir / "assembler.py").is_file()
    assert not list((agent_dir / "sys_prompt").glob("**/*.py"))
    assert (agent_context_dir / "ports.py").is_file()
    assert (agent_context_dir / "attachments.py").is_file()
    assert (agent_context_dir / "history.py").is_file()
    assert (agent_context_dir / "memory.py").is_file()
    assert not (agent_dir / "loop" / "types.py").exists()
    assert (agent_turn_dir / "__init__.py").is_file()
    assert (agent_turn_dir / "executor.py").is_file()
    assert (agent_turn_dir / "lifecycle.py").is_file()
    assert (agent_turn_dir / "persistence.py").is_file()
    assert (agent_turn_dir / "runner.py").is_file()
    assert (agent_turn_dir / "transcript.py").is_file()
    assert (agent_turn_dir / "usage.py").is_file()
    assert (agent_turn_dir / "service.py").is_file()
    assert (agent_turn_dir / "routing.py").is_file()
    assert (agent_session_dir / "__init__.py").is_file()
    assert (agent_session_dir / "service.py").is_file()
    assert not agent_runner_dir.exists()
    assert (agent_tool_dir / "__init__.py").is_file()
    assert not (agent_tool_dir / "callback_context.py").exists()
    assert not (agent_tool_dir / "event_bridge.py").exists()
    assert not (agent_tool_dir / "payloads.py").exists()
    assert not (agent_tool_dir / "projection.py").exists()
    assert not legacy_vendor_dir.exists()
    assert (chat_completions_dir / "__init__.py").is_file()
    assert (chat_completions_dir / "runner.py").is_file()
    assert (chat_completions_dir / "renderer.py").is_file()
    assert not (chat_completions_dir / "event_bridge.py").exists()
    assert not (chat_completions_dir / "payloads.py").exists()
    assert not (agent_turn_dir / "tool_projection.py").exists()
    assert not (package_dir / "application" /
                "agent" / f"{legacy_vendor}_bridge.py").exists()
    assert not (package_dir / "application" /
                "agent" / "tool_payloads.py").exists()
    forbidden_import = "from " + "application.chat"
    for path in (
        agent_dir / "__init__.py",
        agent_turn_dir / "service.py",
        agent_context_dir / "__init__.py",
        agent_context_dir / "loader.py",
    ):
        assert forbidden_import not in path.read_text(encoding="utf-8")
    assert "class AgentIntent(str, Enum)" in routing
    assert "def classify_turn_intent" in routing
    assert not (agent_dir / "results.py").exists()
    assert "AgentTurnResult" not in agent_init
    assert f"{legacy_vendor_title}ToolEventBridge" not in agent_init
    assert "AgentTurnCommand" not in agent_init
    assert not (package_dir / "domain" / "chat").exists()
    assert "class AgentHint" not in routing
    assert "agent_hint" not in routing
    assert "enable_tools" not in routing
    assert "class AgentSessionService" in session_service
    assert "AgentTurnExecutor" in turn_service
    assert "ToolRuntime" in agent_init
    assert "ModelClient" not in agent_init
    assert "ModelStepResult" not in agent_init
    assert "PromptContextManager" not in agent_init
    assert "ToolRuntimePort" not in agent_init
    assert not (agent_dir / "async_bridge.py").exists()
    assert "AgentLoopRequest" not in turn_service
    assert f"{legacy_vendor_title}ToolEventBridge" not in turn_service
    assert "begin_turn_usage_capture" not in turn_service
    assert "_safe_persist_event" not in turn_service
    for path in agent_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert f"from {legacy_vendor}" not in text
        assert "application.agent.loop." + "types" not in text
        assert "application.agent." + "commands" not in text
    assert "class ChatCompletionRole(str, Enum)" in roles
    assert 'TOOL = "tool"' in roles


def test_agent_session_migrations_use_turns_and_session_items_as_canonical_truth():
    """Keep agent session persistence centered on turns/session_items only."""
    chat_migration = (
        AGENT_ROOT / "alembic" / "versions" / "0004_create_chat_sessions.py"
    ).read_text(encoding="utf-8")
    migration = (
        AGENT_ROOT / "alembic" / "versions" / "0007_create_llm_tool_calls.py"
    ).read_text(encoding="utf-8")
    turn_migration = (
        AGENT_ROOT / "alembic" / "versions" / "0011_create_turns_and_session_items.py"
    ).read_text(encoding="utf-8")

    assert '"sessions"' in chat_migration
    assert '"messages"' not in chat_migration
    assert "llm_tool_calls" not in migration
    assert '"turns"' in turn_migration
    assert '"session_items"' in turn_migration
    assert '"model"' in turn_migration
    assert '"provider"' in turn_migration
    assert '"usage"' in turn_migration


def test_number_comparator_is_registered_with_orchestrator_tools():
    """The orchestrator should expose the deterministic number comparison tool."""
    legacy_vendor = "str" + "ands"
    catalog_init = (
        AGENT_ROOT / "src" / "icore_agent" /
        "application" / "agent" / "tool" / "catalog" / "__init__.py"
    ).read_text(encoding="utf-8")
    tool_definition = (
        AGENT_ROOT / "src" / "icore_agent" /
        "domain" / "agent" / "tool" / "tool_definition.py"
    ).read_text(encoding="utf-8")

    assert "build_orchestrator_tools" not in catalog_init
    assert "build_orchestrator_tool_definitions" in catalog_init
    assert "number_comparator" in catalog_init
    assert "orchestrator_tool_names" not in catalog_init
    assert "class ToolDefinition" in tool_definition
    assert "class AgentTool" not in tool_definition
    assert not (
        AGENT_ROOT / "src" / "icore_agent" /
        "application" / "agent" / "tool" / "tool_definition.py"
    ).exists()
    assert f"{legacy_vendor}.types._events" not in tool_definition
    assert "ToolResultEvent" not in tool_definition
    assert "prompt_snippet" in catalog_init
    assert "research_agent_tool" not in catalog_init
    assert "data_agent_tool" not in catalog_init


def test_chat_orchestration_lives_in_application_layer():
    """Keep chat runtime thin while agent owns prompts and tool catalog."""
    legacy_vendor = "str" + "ands"
    package_dir = AGENT_ROOT / "src" / "icore_agent"
    chat_dir = package_dir / "application" / "chat"
    agent_dir = package_dir / "application" / "agent"
    dependencies = (
        package_dir / "interfaces" / "http" / "v1" / "dependencies.py"
    ).read_text(
        encoding="utf-8"
    )
    chat_completions_runner = (
        package_dir / "infrastructure" / "agent" / "chat_completions" / "runner.py"
    ).read_text(encoding="utf-8")
    domain_prompt = (
        package_dir / "domain" / "agent" / "prompt" / "system_prompt.py"
    ).read_text(encoding="utf-8")
    domain_prompt_init = (
        package_dir / "domain" / "agent" / "prompt" / "__init__.py"
    ).read_text(encoding="utf-8")
    domain_tool_dir = package_dir / "domain" / "agent" / "tool"
    domain_tool_init = (domain_tool_dir / "__init__.py").read_text(
        encoding="utf-8"
    )
    prompt_envelope = (
        package_dir / "domain" / "agent" / "prompt" / "prompt_envelope.py"
    ).read_text(encoding="utf-8")
    catalog_dir = agent_dir / "tool" / "catalog"
    agent_session_dir = package_dir / "domain" / "agent" / "session"
    session_items_dir = agent_session_dir / "session_items"
    application_agent_context_dir = agent_dir / "context"
    domain_context_dir = package_dir / "domain" / "agent" / "context"

    assert not (package_dir / "engine").exists()
    assert not (package_dir / "tools").exists()
    chat_sources = list(chat_dir.rglob("*.py")) if chat_dir.exists() else []
    assert chat_sources == []
    assert (catalog_dir / "web_search.py").is_file()
    assert not (agent_dir / "sequential").exists()
    assert "create_chat_completions_model_client" in dependencies
    assert f"create_{legacy_vendor}_orchestrator" not in dependencies
    assert "ModuleNotFoundError" not in chat_completions_runner
    assert "_Fallback" not in chat_completions_runner
    assert "ORCHESTRATOR_SYSTEM_PROMPT_BASE" not in chat_completions_runner
    assert "sub-agent" not in chat_completions_runner
    assert "build_system_prompt" not in chat_completions_runner
    assert "class BuildSystemPromptOptions" not in domain_prompt
    assert "class SystemPrompt" not in domain_prompt
    assert "class PromptSource" not in domain_prompt
    assert "def base_system_prompt" not in domain_prompt
    assert "def build_tool_use_rules" not in domain_prompt
    assert "def build_base_instructions" in domain_prompt
    assert "BuildSystemPromptOptions" not in domain_prompt_init
    assert "build_runtime_context_prompt" not in domain_prompt
    assert "ORCHESTRATOR_SYSTEM_PROMPT_BASE" in domain_prompt
    assert "RESEARCH_SYSTEM_PROMPT" not in domain_prompt
    assert "SEQUENTIAL_SYSTEM_PROMPT" not in domain_prompt
    assert (domain_tool_dir / "tool_definition.py").is_file()
    assert "ToolDefinition" in domain_tool_init
    assert "ToolChoice" in domain_tool_init
    assert "class ToolSpec" not in prompt_envelope
    assert "list[ToolDefinition]" in prompt_envelope
    assert not (agent_dir / "tool" / "tool_definition.py").exists()
    assert not (agent_session_dir / "session_item.py").exists()
    assert (session_items_dir / "user_message_item.py").is_file()
    assert (session_items_dir / "universal_session_item.py").is_file()
    assert "def to_text" in (
        session_items_dir / "user_message_item.py"
    ).read_text(encoding="utf-8")
    assert not (application_agent_context_dir / "agent_context.py").exists()
    assert (domain_context_dir / "agent_context.py").is_file()
    assert "class AgentContext" in (
        domain_context_dir / "agent_context.py"
    ).read_text(encoding="utf-8")
    assert "def build_prompt_envelope" in (
        domain_context_dir / "agent_context.py"
    ).read_text(encoding="utf-8")


def test_python_sources_do_not_import_top_level_domain_package():
    """Keep package imports anchored at icore_agent, not a nonexistent domain."""
    package_dir = AGENT_ROOT / "src" / "icore_agent"
    offenders: list[str] = []
    for source in package_dir.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        if "from domain." in text or "import domain." in text:
            offenders.append(str(source.relative_to(package_dir)))

    assert offenders == []


def test_agent_session_schema_uses_explicit_payload_models():
    """Keep session response schemas from exposing untyped list[dict] fields."""
    schema = (
        AGENT_ROOT
        / "src"
        / "icore_agent"
        / "interfaces"
        / "http"
        / "v1"
        / "agent"
        / "schemas"
        / "session.py"
    ).read_text(encoding="utf-8")

    assert "class SessionTurnItem" in schema
    assert "class SessionTimelineItem" in schema
    assert "class SessionAttachmentItem" in schema
    assert "turns: list[SessionTurnItem]" in schema
    assert "messages:" not in schema
    assert "attachments: list[SessionAttachmentItem]" in schema
    assert "list[dict]" not in schema


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
    auth_schema = (
        package_dir / "interfaces" / "http" / "v1" /
        "account" / "schemas" / "auth.py"
    ).read_text(encoding="utf-8")
    persistence_dir = package_dir / "infrastructure" / "persistence" / "users"

    assert "serialize_user_profile" in serializer
    assert "UserProfile" in serializer
    assert "class UserProfilePayload" in auth_schema
    assert "user: dict" not in auth_schema
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
    assert "dotenv/**/.env.*" in dockerignore
    assert "!dotenv/**/.env.*.example" in dockerignore
