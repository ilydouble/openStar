from __future__ import annotations

from dataclasses import dataclass

from icore_agent.application.commerce import (
    CommerceDiagnosisService,
    commerce_diagnosis_profile,
)
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
