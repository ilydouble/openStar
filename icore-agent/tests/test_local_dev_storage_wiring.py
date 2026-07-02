from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_start_dev_loads_storage_and_logging_dotenv_domains() -> None:
    """Local backend startup should load file storage and logging service URLs."""
    script = (PROJECT_ROOT / "start-dev.sh").read_text(encoding="utf-8")

    assert '"dotenv/dev/.env.storage"' in script
    assert '"dotenv/dev/.env.logging"' in script
    assert "STORAGE_SERVICE_URL" in script
    assert "LOGGING_SERVICE_URL" in script


def test_dev_storage_and_logging_services_publish_host_ports() -> None:
    """Local FastAPI can reach helper Go services through localhost ports."""
    storage_compose = (
        PROJECT_ROOT
        / "infrastructure/docker/compose/dev/storage-service.yml"
    ).read_text(encoding="utf-8")
    logging_compose = (
        PROJECT_ROOT
        / "infrastructure/docker/compose/dev/logging-service.yml"
    ).read_text(encoding="utf-8")

    assert "STORAGE_SERVICE_PORT_BIND" in storage_compose
    assert "127.0.0.1:18090:8090" in storage_compose
    assert "LOGGING_SERVICE_PORT_BIND" in logging_compose
    assert "127.0.0.1:18091:8091" in logging_compose
