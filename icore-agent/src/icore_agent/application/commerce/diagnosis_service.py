"""Application service for Commerce operating diagnosis workflows."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

from icore_agent.domain.commerce import CommerceDiagnosisReport
from icore_agent.domain.identifiers import uuid7

from .agent_profile import commerce_diagnosis_profile

LOW_MARGIN_THRESHOLD = Decimal("0.20")
SAMPLE_CSV = (
    "sku,product,orders,revenue,cost,inventory,daily_sales,supplier,lead_time_days\n"
    "TRVL-CABLE-3P,Travel cable pack,30,900,450,4,2,Shenzhen Brightline,10\n"
    "DESK-LAMP-MINI,Mini desk lamp,5,100,85,80,0.5,Guangzhou Northstar,15\n"
    "PACK-CUBE-SET,Packing cube set,60,600,540,100,1,Ningbo Packwell,30\n"
).encode()


@dataclass(frozen=True)
class CommerceRow:
    """Normalized row used by deterministic Commerce diagnostics."""

    sku: str
    product: str
    orders: int
    revenue: Decimal
    cost: Decimal
    inventory: Decimal
    daily_sales: Decimal
    supplier: str
    lead_time_days: Decimal

    @property
    def gross_margin_rate(self) -> Decimal:
        """Return row-level gross margin rate."""
        if self.revenue <= 0:
            return Decimal("0")
        return (self.revenue - self.cost) / self.revenue

    @property
    def days_left(self) -> Decimal | None:
        """Return inventory coverage in days when sales velocity is available."""
        if self.daily_sales <= 0:
            return None
        return self.inventory / self.daily_sales


class CommerceDiagnosisService:
    """Generate Commerce operating diagnoses from uploaded CSV files."""

    def __init__(self, *, file_service: Any) -> None:
        """Create the service with a user-owned file asset reader."""
        self._file_service = file_service

    def create_diagnosis(
        self,
        *,
        user_id: str,
        file_uuid: str,
        locale: str = "zh-CN",
    ) -> CommerceDiagnosisReport:
        """Create a synchronous V1 diagnosis from one uploaded CSV file."""
        asset = self._file_service.get_owned_asset(
            uploader_public_id=user_id,
            file_uuid=file_uuid,
            allow_pending=False,
        )
        rows = _parse_csv(
            self._file_service.read_file_bytes(
                uploader_public_id=user_id,
                file_uuid=file_uuid,
            )
        )
        return _build_report(
            rows,
            source_file={
                "file_uuid": file_uuid,
                "filename": asset.original_filename,
                "row_count": len(rows),
            },
            locale=locale,
        )

    def create_sample_diagnosis(
        self,
        *,
        locale: str = "zh-CN",
    ) -> CommerceDiagnosisReport:
        """Create a V1 sample diagnosis without uploaded-file infrastructure."""
        rows = _parse_csv(SAMPLE_CSV)
        return _build_report(
            rows,
            source_file={
                "sample": True,
                "filename": "commerce-sample.csv",
                "row_count": len(rows),
            },
            locale=locale,
        )


def _build_report(
    rows: list[CommerceRow],
    *,
    source_file: dict[str, Any],
    locale: str,
) -> CommerceDiagnosisReport:
    """Build a Commerce diagnosis report from normalized CSV rows."""
    metrics = _summarize_metrics(rows)
    risks = _detect_risks(rows)
    tasks = _build_tasks(risks)
    profile = commerce_diagnosis_profile()
    return CommerceDiagnosisReport(
        diagnosis_id=str(uuid7()),
        agent_profile=profile.id,
        source_file=source_file,
        metrics=metrics,
        risks=risks,
        tasks=tasks,
        report_summary=_build_summary(metrics, risks, locale=locale),
    )


def _parse_csv(body: bytes) -> list[CommerceRow]:
    """Parse uploaded CSV bytes into normalized Commerce rows."""
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or missing headers")
    rows = [_row_from_mapping(row, index)
            for index, row in enumerate(reader, 2)]
    if not rows:
        raise ValueError("CSV file has no data rows")
    return rows


def _row_from_mapping(row: dict[str, str], line_no: int) -> CommerceRow:
    """Normalize one CSV row into the Commerce diagnosis schema."""
    normalized = {_normalize_key(key): value for key, value in row.items()}
    sku = _text(normalized, "sku")
    if not sku:
        raise ValueError(f"CSV line {line_no} is missing sku")
    revenue = _decimal(normalized, "revenue")
    cost = _decimal(normalized, "cost")
    inventory = _decimal(normalized, "inventory")
    daily_sales = _decimal(normalized, "daily_sales")
    return CommerceRow(
        sku=sku,
        product=_text(normalized, "product") or sku,
        orders=int(_decimal(normalized, "orders")),
        revenue=revenue,
        cost=cost,
        inventory=inventory,
        daily_sales=daily_sales,
        supplier=_text(normalized, "supplier"),
        lead_time_days=_decimal(normalized, "lead_time_days"),
    )


def _summarize_metrics(rows: list[CommerceRow]) -> dict[str, Any]:
    """Calculate deterministic top-level Commerce operating metrics."""
    total_revenue = sum((row.revenue for row in rows), Decimal("0"))
    total_cost = sum((row.cost for row in rows), Decimal("0"))
    total_orders = sum(row.orders for row in rows)
    margin_rate = (
        (total_revenue - total_cost) / total_revenue
        if total_revenue > 0
        else Decimal("0")
    )
    return {
        "sku_count": len(rows),
        "total_revenue": _float(total_revenue),
        "total_orders": total_orders,
        "gross_margin_rate": _float(margin_rate, places=4),
    }


def _detect_risks(rows: list[CommerceRow]) -> list[dict[str, Any]]:
    """Detect V1 inventory and margin risks from normalized rows."""
    risks: list[dict[str, Any]] = []
    for row in rows:
        days_left = row.days_left
        if days_left is not None and days_left <= row.lead_time_days:
            risks.append({
                "type": "stockout",
                "severity": "high" if days_left <= row.lead_time_days / 2 else "medium",
                "sku": row.sku,
                "product": row.product,
                "supplier": row.supplier,
                "days_left": _float(days_left, places=1),
                "lead_time_days": _float(row.lead_time_days, places=1),
                "message": (
                    f"{row.sku} inventory covers about "
                    f"{_float(days_left, places=1)} days, below supplier lead time."
                ),
            })
        if row.gross_margin_rate < LOW_MARGIN_THRESHOLD:
            risks.append({
                "type": "low_margin",
                "severity": "medium",
                "sku": row.sku,
                "product": row.product,
                "gross_margin_rate": _float(row.gross_margin_rate, places=4),
                "message": (
                    f"{row.sku} gross margin is "
                    f"{_float(row.gross_margin_rate * 100, places=1)}%."
                ),
            })
    return sorted(risks, key=_risk_sort_key)


def _build_tasks(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build action tasks from diagnosis risks."""
    tasks: list[dict[str, Any]] = []
    for risk in risks:
        if risk["type"] == "stockout":
            tasks.append({
                "type": "replenishment",
                "title": f"Replenish {risk['sku']}",
                "priority": "high" if risk["severity"] == "high" else "medium",
                "body": (
                    "Confirm available supplier capacity and place a replenishment "
                    "order before inventory coverage falls below the lead time."
                ),
                "source_risk": risk["type"],
                "sku": risk["sku"],
            })
        elif risk["type"] == "low_margin":
            tasks.append({
                "type": "margin_review",
                "title": f"Review margin for {risk['sku']}",
                "priority": "medium",
                "body": (
                    "Check landed cost, promotion pressure, and pricing before "
                    "scaling this SKU."
                ),
                "source_risk": risk["type"],
                "sku": risk["sku"],
            })
    return tasks


def _build_summary(
    metrics: dict[str, Any],
    risks: list[dict[str, Any]],
    *,
    locale: str,
) -> str:
    """Build a concise human-readable diagnosis summary."""
    primary = risks[0] if risks else None
    if locale == "zh-CN":
        if primary:
            return (
                f"本次诊断覆盖 {metrics['sku_count']} 个 SKU，销售额 "
                f"{metrics['total_revenue']}，发现首要风险 {primary['sku']} "
                f"({primary['type']})，建议优先处理。"
            )
        return (
            f"本次诊断覆盖 {metrics['sku_count']} 个 SKU，暂未发现高优先级运营风险。"
        )
    if primary:
        return (
            f"Diagnosis covers {metrics['sku_count']} SKUs. The first priority is "
            f"{primary['sku']} ({primary['type']})."
        )
    return f"Diagnosis covers {metrics['sku_count']} SKUs with no high-priority risk."


def _text(row: dict[str, str], key: str) -> str:
    """Return a stripped text cell value."""
    return str(row.get(key) or "").strip()


def _decimal(row: dict[str, str], key: str) -> Decimal:
    """Return a decimal cell value, defaulting blank numeric cells to zero."""
    raw = _text(row, key)
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"CSV column {key} must be numeric") from exc


def _normalize_key(key: str | None) -> str:
    """Normalize CSV headers into snake-like lookup keys."""
    return str(key or "").strip().lower().replace(" ", "_").replace("-", "_")


def _float(value: Decimal, *, places: int = 2) -> float:
    """Return a rounded JSON-friendly float."""
    quant = Decimal("1").scaleb(-places)
    return float(value.quantize(quant))


def _risk_sort_key(risk: dict[str, Any]) -> tuple[int, str]:
    """Sort high-severity risks first while keeping SKU order stable."""
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return severity_rank.get(str(risk.get("severity")), 9), str(risk.get("sku"))
