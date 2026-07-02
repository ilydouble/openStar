from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from icore_agent.domain.commerce import CommerceDiagnosisReport
from icore_agent.domain.user import AuthenticatedUser
from icore_agent.interfaces.http.v1.commerce.handlers import (
    get_commerce_current_user,
    get_commerce_diagnosis_service,
)
from icore_agent.interfaces.http.v1.router import include_api_routers


def _build_app() -> FastAPI:
    """Build a router-only test app without global auth middleware."""
    test_app = FastAPI()
    include_api_routers(test_app)
    return test_app


def _api_data(resp) -> dict:
    """Return the ApiEnvelope data object from a test response."""
    payload = resp.json()
    assert payload["code"] == resp.status_code
    assert payload["message"]
    assert payload["timestamp"]
    return payload["data"]


class FakeCommerceDiagnosisService:
    """Fake Commerce diagnosis service for HTTP contract tests."""

    def __init__(self) -> None:
        """Initialize fake call recording."""
        self.agent_calls = []

    async def create_agent_diagnosis(self, **kwargs) -> CommerceDiagnosisReport:
        """Return a deterministic agent-backed diagnosis report."""
        self.agent_calls.append(kwargs)
        assert kwargs["user_id"] == "user-123"
        assert kwargs["file_uuids"] in (
            ["file-123"],
            ["sales-file", "inventory-file"],
        )
        assert kwargs["locale"] == "zh-CN"
        if kwargs["file_uuids"] == ["sales-file", "inventory-file"]:
            return self.create_diagnosis_for_files(**kwargs)
        return self.create_diagnosis(
            user_id=kwargs["user_id"],
            file_uuid=kwargs["file_uuids"][0],
            locale=kwargs["locale"],
        )

    def create_diagnosis(self, **kwargs) -> CommerceDiagnosisReport:
        """Return a deterministic diagnosis report."""
        assert kwargs["user_id"] == "user-123"
        assert kwargs["file_uuid"] == "file-123"
        assert kwargs["locale"] == "zh-CN"
        return CommerceDiagnosisReport(
            diagnosis_id="diagnosis-123",
            agent_profile="commerce_diagnosis_v1",
            source_file={"file_uuid": "file-123",
                         "filename": "orders.csv", "row_count": 3},
            metrics={"sku_count": 3, "total_revenue": 1600.0},
            risks=[{"type": "stockout", "sku": "SKU-A", "severity": "high"}],
            tasks=[{"type": "replenishment", "sku": "SKU-A", "priority": "high"}],
            report_summary="本次诊断覆盖 3 个 SKU，发现首要风险 SKU-A。",
        )

    def create_diagnosis_for_files(self, **kwargs) -> CommerceDiagnosisReport:
        """Return a deterministic multi-file diagnosis report."""
        assert kwargs["user_id"] == "user-123"
        assert kwargs["file_uuids"] == ["sales-file", "inventory-file"]
        assert kwargs["locale"] == "zh-CN"
        return CommerceDiagnosisReport(
            diagnosis_id="diagnosis-multi-123",
            agent_profile="commerce_diagnosis_v1",
            source_file={
                "file_uuids": ["sales-file", "inventory-file"],
                "filename": "daily_sales_report.csv + 1",
                "row_count": 3,
                "available_sources": ["inventory", "sales"],
                "missing_sources": ["ads", "logistics"],
            },
            metrics={"sku_count": 2, "total_revenue": 600.0},
            risks=[{"type": "stockout", "sku": "SKU-A", "severity": "high"}],
            tasks=[{"type": "replenishment", "sku": "SKU-A", "priority": "high"}],
            report_summary="本次诊断覆盖 2 个 SKU，缺少 ads、logistics 数据。",
        )

    def create_sample_diagnosis(self, **kwargs) -> CommerceDiagnosisReport:
        """Return a deterministic sample diagnosis report."""
        assert kwargs["locale"] == "zh-CN"
        return CommerceDiagnosisReport(
            diagnosis_id="sample-diagnosis-123",
            agent_profile="commerce_diagnosis_v1",
            source_file={"sample": True,
                         "filename": "commerce-sample.csv", "row_count": 3},
            metrics={"sku_count": 3, "total_revenue": 1600.0},
            risks=[{"type": "stockout", "sku": "SKU-SAMPLE", "severity": "high"}],
            tasks=[{"type": "replenishment",
                    "sku": "SKU-SAMPLE", "priority": "high"}],
            report_summary="本次诊断覆盖 3 个 SKU，发现首要风险 SKU-SAMPLE。",
        )


@pytest.mark.asyncio
async def test_commerce_diagnosis_requires_auth() -> None:
    """Commerce diagnosis endpoint should be protected."""
    test_app = _build_app()
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/commerce/diagnoses",
            json={"file_uuid": "file-123"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_commerce_diagnosis_returns_agent_report_envelope() -> None:
    """Commerce diagnosis endpoint should return a structured agent report."""
    test_app = _build_app()

    async def fake_current_user() -> AuthenticatedUser:
        """Return the current test user."""
        return AuthenticatedUser(
            public_id="user-123",
            email="user@example.com",
            name="User One",
            roles=("owner",),
        )

    async def fake_service() -> FakeCommerceDiagnosisService:
        """Return the fake Commerce diagnosis service."""
        return FakeCommerceDiagnosisService()

    test_app.dependency_overrides[get_commerce_current_user] = fake_current_user
    test_app.dependency_overrides[get_commerce_diagnosis_service] = fake_service
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/commerce/diagnoses",
            json={"file_uuid": "file-123", "locale": "zh-CN"},
        )

    assert resp.status_code == 200, resp.text
    data = _api_data(resp)
    assert data["agent_profile"] == "commerce_diagnosis_v1"
    assert data["source_file"]["filename"] == "orders.csv"
    assert data["risks"][0]["sku"] == "SKU-A"
    assert data["tasks"][0]["type"] == "replenishment"


@pytest.mark.asyncio
async def test_commerce_diagnosis_accepts_multiple_file_uuids() -> None:
    """Commerce diagnosis endpoint should accept a batch of uploaded CSV files."""
    test_app = _build_app()

    async def fake_current_user() -> AuthenticatedUser:
        """Return the current test user."""
        return AuthenticatedUser(
            public_id="user-123",
            email="user@example.com",
            name="User One",
            roles=("owner",),
        )

    async def fake_service() -> FakeCommerceDiagnosisService:
        """Return the fake Commerce diagnosis service."""
        return FakeCommerceDiagnosisService()

    test_app.dependency_overrides[get_commerce_current_user] = fake_current_user
    test_app.dependency_overrides[get_commerce_diagnosis_service] = fake_service
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/commerce/diagnoses",
            json={
                "file_uuids": ["sales-file", "inventory-file"],
                "locale": "zh-CN",
            },
        )

    assert resp.status_code == 200, resp.text
    data = _api_data(resp)
    assert data["source_file"]["file_uuids"] == [
        "sales-file", "inventory-file"]
    assert data["source_file"]["missing_sources"] == ["ads", "logistics"]
    assert data["metrics"]["sku_count"] == 2


@pytest.mark.asyncio
async def test_sample_commerce_diagnosis_returns_report_without_upload() -> None:
    """Sample Commerce diagnosis should not require a file upload first."""
    test_app = _build_app()

    async def fake_current_user() -> AuthenticatedUser:
        """Return the current test user."""
        return AuthenticatedUser(
            public_id="user-123",
            email="user@example.com",
            name="User One",
            roles=("owner",),
        )

    async def fake_service() -> FakeCommerceDiagnosisService:
        """Return the fake Commerce diagnosis service."""
        return FakeCommerceDiagnosisService()

    test_app.dependency_overrides[get_commerce_current_user] = fake_current_user
    test_app.dependency_overrides[get_commerce_diagnosis_service] = fake_service
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/commerce/diagnoses/sample",
            json={"locale": "zh-CN"},
        )

    assert resp.status_code == 200, resp.text
    data = _api_data(resp)
    assert data["source_file"]["sample"] is True
    assert data["source_file"]["filename"] == "commerce-sample.csv"
    assert data["risks"][0]["sku"] == "SKU-SAMPLE"
