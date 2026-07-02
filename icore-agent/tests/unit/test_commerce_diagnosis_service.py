from __future__ import annotations

from dataclasses import dataclass

import pytest

from icore_agent.application.commerce import (
    CommerceDiagnosisService,
    commerce_diagnosis_profile,
)
from icore_agent.domain.agent.loop import ModelStepResult
from icore_agent.domain.agent.session import AgentMessageItem
from icore_agent.domain.files import FileAsset


@dataclass(frozen=True)
class FakeFileAsset:
    """Minimal file asset value for commerce diagnosis tests."""

    file_uuid: str
    original_filename: str


class FakeFileService:
    """Fake uploaded-file service that returns one completed CSV asset."""

    def __init__(self, body: bytes) -> None:
        """Initialize the fake with deterministic CSV bytes."""
        self.body = body
        self.asset = FakeFileAsset(
            file_uuid="file-123",
            original_filename="orders.csv",
        )

    def get_owned_asset(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
        allow_pending: bool = False,
    ) -> FileAsset:
        """Return a fake owned file asset."""
        assert uploader_public_id == "user-123"
        assert file_uuid == "file-123"
        assert allow_pending is False
        return self.asset  # type: ignore[return-value]

    def read_file_bytes(self, *, uploader_public_id: str, file_uuid: str) -> bytes:
        """Return CSV bytes for the owned file."""
        assert uploader_public_id == "user-123"
        assert file_uuid == "file-123"
        return self.body


class MultiFileService:
    """Fake uploaded-file service that returns several completed CSV assets."""

    def __init__(self, files: dict[str, tuple[str, bytes]]) -> None:
        """Initialize the fake with file UUIDs mapped to filenames and bytes."""
        self.files = files

    def get_owned_asset(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
        allow_pending: bool = False,
    ) -> FileAsset:
        """Return the requested fake owned file asset."""
        assert uploader_public_id == "user-123"
        assert allow_pending is False
        filename, _body = self.files[file_uuid]
        return FakeFileAsset(
            file_uuid=file_uuid,
            original_filename=filename,
        )  # type: ignore[return-value]

    def read_file_bytes(self, *, uploader_public_id: str, file_uuid: str) -> bytes:
        """Return CSV bytes for the requested owned file."""
        assert uploader_public_id == "user-123"
        return self.files[file_uuid][1]


class FakeCommerceModelClient:
    """Fake model client that records Commerce evidence prompts."""

    def __init__(self, text: str) -> None:
        """Initialize the fake with one assistant response."""
        self.text = text
        self.envelopes = []

    async def sample(self, envelope):
        """Record the prompt envelope and return the scripted response."""
        self.envelopes.append(envelope)
        return ModelStepResult(
            assistant_item=AgentMessageItem(text=self.text),
            model="fake-commerce-model",
            provider="fake",
        )


class FakeCommerceModelFactory:
    """Fake model client factory for Commerce agent tests."""

    def __init__(self, text: str) -> None:
        """Initialize the factory with a scripted model client."""
        self.client = FakeCommerceModelClient(text)
        self.calls = []

    def __call__(self, **kwargs):
        """Record factory kwargs and return the fake model client."""
        self.calls.append(kwargs)
        return self.client


class MemoryDiagnosisRepository:
    """In-memory Commerce diagnosis repository for service tests."""

    def __init__(self) -> None:
        """Initialize empty report storage."""
        self.saved: list[tuple[str, object]] = []

    def save(self, user_id: str, report):
        """Record and return one persisted report."""
        self.saved.append((user_id, report))
        return report

    def get_latest_for_user(self, user_id: str):
        """Return the most recently saved report for one user."""
        for saved_user_id, report in reversed(self.saved):
            if saved_user_id == user_id:
                return report
        return None


def test_commerce_diagnosis_summarizes_metrics_risks_and_tasks() -> None:
    """Commerce diagnosis should turn uploaded CSV rows into an operating report."""
    csv_body = (
        "sku,product,orders,revenue,cost,inventory,daily_sales,supplier,lead_time_days\n"
        "SKU-A,Widget A,30,900,450,4,2,Supplier A,10\n"
        "SKU-B,Widget B,5,100,85,80,0.5,Supplier B,15\n"
        "SKU-C,Widget C,60,600,540,100,1,Supplier C,30\n"
    ).encode()
    service = CommerceDiagnosisService(file_service=FakeFileService(csv_body))

    report = service.create_diagnosis(
        user_id="user-123",
        file_uuid="file-123",
        locale="zh-CN",
    )

    assert report.agent_profile == "commerce_diagnosis_v1"
    assert report.source_file["filename"] == "orders.csv"
    assert report.metrics["sku_count"] == 3
    assert report.metrics["total_revenue"] == 1600.0
    assert report.metrics["total_orders"] == 95
    assert report.metrics["gross_margin_rate"] == 0.3281
    assert report.risks[0]["type"] == "stockout"
    assert report.risks[0]["sku"] == "SKU-A"
    assert report.risks[0]["severity"] == "high"
    assert any(task["type"] == "replenishment" for task in report.tasks)
    assert any(task["type"] == "margin_review" for task in report.tasks)
    assert "SKU-A" in report.report_summary


def test_sample_commerce_diagnosis_does_not_require_file_service() -> None:
    """Sample diagnosis should work without uploaded-file infrastructure."""
    service = CommerceDiagnosisService(file_service=None)

    report = service.create_sample_diagnosis(locale="zh-CN")

    assert report.agent_profile == "commerce_diagnosis_v1"
    assert report.source_file["sample"] is True
    assert report.source_file["filename"] == "commerce-sample.csv"
    assert report.metrics["sku_count"] == 3
    assert report.risks[0]["sku"] == "TRVL-CABLE-3P"
    assert any(task["type"] == "replenishment" for task in report.tasks)


def test_sample_commerce_diagnosis_can_be_persisted_for_user() -> None:
    """Sample diagnosis should use the configured persistence repository."""
    repository = MemoryDiagnosisRepository()
    service = CommerceDiagnosisService(
        file_service=None,
        diagnosis_repository=repository,
    )

    report = service.create_sample_diagnosis_for_user(
        user_id="user-123",
        locale="zh-CN",
    )

    assert repository.saved == [("user-123", report)]
    assert report.source_file["analysis_mode"] == "sample"
    assert service.get_latest_diagnosis(user_id="user-123") == report


def test_commerce_diagnosis_accepts_common_chinese_csv_headers() -> None:
    """Commerce diagnosis should map common Chinese CSV headers to canonical fields."""
    csv_body = (
        "商品编号,商品名称,订单量,销售额,成本,库存,日均销量,供应商,交期天数\n"
        "SKU-A,旅行线缆套装,30,900,450,4,2,深圳供应商,10\n"
        "SKU-B,桌面小灯,5,100,85,80,0.5,广州供应商,15\n"
    ).encode()
    service = CommerceDiagnosisService(file_service=FakeFileService(csv_body))

    report = service.create_diagnosis(
        user_id="user-123",
        file_uuid="file-123",
        locale="zh-CN",
    )

    assert report.metrics["sku_count"] == 2
    assert report.metrics["total_revenue"] == 1000.0
    assert report.risks[0]["sku"] == "SKU-A"
    assert report.risks[0]["type"] == "stockout"


def test_commerce_diagnosis_accepts_ad_csv_without_sku() -> None:
    """Commerce diagnosis should accept campaign-level CSVs that have no SKU column."""
    csv_body = (
        "date,campaign_id,campaign_name,channel,spend_usd,orders,revenue_usd\n"
        "2026-06-15,CAM-NA,Summer Travel Essentials,Amazon PPC,223.15,309,9541.06\n"
        "2026-06-15,CAM-EU,Summer Travel Essentials,Amazon PPC,165.70,7,151.08\n"
    ).encode()
    service = CommerceDiagnosisService(file_service=FakeFileService(csv_body))

    report = service.create_diagnosis(
        user_id="user-123",
        file_uuid="file-123",
        locale="zh-CN",
    )

    assert report.metrics["sku_count"] == 2
    assert report.metrics["total_orders"] == 316
    assert report.metrics["total_revenue"] == 9692.14
    assert report.risks[0]["sku"] == "CAM-EU"
    assert report.risks[0]["type"] == "low_margin"


def test_commerce_diagnosis_maps_inventory_report_headers() -> None:
    """Commerce diagnosis should map replenishment CSV stock and velocity headers."""
    csv_body = (
        "sku,product,current_stock,daily_sales_avg,supplier,lead_time_days\n"
        "TRVL-CABLE-3P,Travel cable pack,27,3.27,Shenzhen Brightline,10\n"
    ).encode()
    service = CommerceDiagnosisService(file_service=FakeFileService(csv_body))

    report = service.create_diagnosis(
        user_id="user-123",
        file_uuid="file-123",
        locale="zh-CN",
    )

    assert report.metrics["sku_count"] == 1
    assert report.risks[0]["sku"] == "TRVL-CABLE-3P"
    assert report.risks[0]["type"] == "stockout"
    assert report.risks[0]["days_left"] == 8.3


def test_commerce_diagnosis_combines_available_csv_reports() -> None:
    """Commerce diagnosis should analyze every uploaded report and flag missing ones."""
    sales_csv = (
        "sku,product,orders,revenue,cost\n"
        "SKU-A,Widget A,10,500,300\n"
        "SKU-B,Widget B,5,100,90\n"
    ).encode()
    inventory_csv = (
        "sku,product,current_stock,daily_sales_avg,supplier,lead_time_days\n"
        "SKU-A,Widget A,4,2,Supplier A,10\n"
    ).encode()
    service = CommerceDiagnosisService(
        file_service=MultiFileService({
            "sales-file": ("daily_sales_report.csv", sales_csv),
            "inventory-file": ("inventory_replenishment_alert.csv", inventory_csv),
        })
    )

    report = service.create_diagnosis(
        user_id="user-123",
        file_uuids=["sales-file", "inventory-file"],
        locale="zh-CN",
    )

    assert report.source_file["file_uuids"] == ["sales-file", "inventory-file"]
    assert report.source_file["row_count"] == 3
    assert report.source_file["available_sources"] == ["inventory", "sales"]
    assert report.source_file["missing_sources"] == ["ads", "logistics"]
    assert report.metrics["sku_count"] == 2
    assert report.metrics["total_revenue"] == 600.0
    assert report.metrics["total_orders"] == 15
    assert any(risk["type"] == "stockout" and risk["sku"]
               == "SKU-A" for risk in report.risks)
    assert "缺少 ads、logistics 数据" in report.report_summary


def test_commerce_diagnosis_prefers_sales_metrics_when_ads_report_is_present() -> None:
    """Top-level revenue should use sales data instead of adding ad-attributed revenue."""
    ads_csv = (
        "campaign_id,campaign_name,spend_usd,orders,revenue_usd\n"
        "CAM-1,Launch Ads,20,2,1000\n"
    ).encode()
    sales_csv = (
        "sku,product,orders,revenue,cost\n"
        "SKU-A,Widget A,3,120,60\n"
    ).encode()
    service = CommerceDiagnosisService(
        file_service=MultiFileService({
            "ads-file": ("ads_traffic_performance.csv", ads_csv),
            "sales-file": ("daily_sales_report.csv", sales_csv),
        })
    )

    report = service.create_diagnosis(
        user_id="user-123",
        file_uuids=["ads-file", "sales-file"],
        locale="zh-CN",
    )

    assert report.source_file["available_sources"] == ["ads", "sales"]
    assert report.metrics["sku_count"] == 1
    assert report.metrics["total_revenue"] == 120.0
    assert report.metrics["total_orders"] == 3
    assert report.metrics["gross_margin_rate"] == 0.5


@pytest.mark.asyncio
async def test_commerce_agent_uses_model_to_review_evidence_packet() -> None:
    """Commerce diagnosis should invoke the model agent with structured evidence."""
    sales_csv = (
        "sku,product,orders,revenue,cost\n"
        "SKU-A,Widget A,3,120,60\n"
    ).encode()
    model_factory = FakeCommerceModelFactory(
        '{"report_summary":"智能体判断：SKU-A 应优先补货。",'
        '"tasks":[{"type":"agent_follow_up","title":"检查 SKU-A 补货",'
        '"priority":"high","body":"基于销售和库存证据处理 SKU-A。","sku":"SKU-A"}]}'
    )
    service = CommerceDiagnosisService(
        file_service=MultiFileService({
            "sales-file": ("daily_sales_report.csv", sales_csv),
        }),
        model_client_factory=model_factory,
    )

    report = await service.create_agent_diagnosis(
        user_id="user-123",
        file_uuids=["sales-file"],
        locale="zh-CN",
    )

    assert model_factory.calls[0]["user_id"] == "user-123"
    assert model_factory.client.envelopes
    prompt_text = model_factory.client.envelopes[0].current_user_item.to_text()
    assert '"available_sources": ["sales"]' in prompt_text
    assert '"missing_sources": ["ads", "inventory", "logistics"]' in prompt_text
    assert report.report_summary == "智能体判断：SKU-A 应优先补货。"
    assert report.tasks[0]["type"] == "agent_follow_up"
    assert report.source_file["analysis_mode"] == "agent"
    assert report.source_file["agent_model"] == "fake-commerce-model"


@pytest.mark.asyncio
async def test_commerce_agent_persists_generated_diagnosis_report() -> None:
    """Commerce agent diagnosis should save a report snapshot for later reads."""
    sales_csv = (
        "sku,product,orders,revenue,cost\n"
        "SKU-A,Widget A,3,120,60\n"
    ).encode()
    repository = MemoryDiagnosisRepository()
    service = CommerceDiagnosisService(
        file_service=MultiFileService({
            "sales-file": ("daily_sales_report.csv", sales_csv),
        }),
        diagnosis_repository=repository,
    )

    report = await service.create_agent_diagnosis(
        user_id="user-123",
        file_uuids=["sales-file"],
        locale="zh-CN",
    )

    assert repository.saved == [("user-123", report)]
    assert service.get_latest_diagnosis(user_id="user-123") == report


def test_commerce_agent_profile_declares_workflow_and_tools() -> None:
    """Commerce agent profile should describe its dedicated workflow and tools."""
    profile = commerce_diagnosis_profile()

    assert profile.id == "commerce_diagnosis_v1"
    assert profile.workflow_steps == (
        "load_uploaded_csv",
        "profile_operating_metrics",
        "detect_inventory_and_margin_risks",
        "generate_report_and_tasks",
    )
    assert profile.tool_names == (
        "read_uploaded_file",
        "csv_profile",
        "sales_kpi_analyzer",
        "inventory_risk_analyzer",
    )
