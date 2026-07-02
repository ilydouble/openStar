"""Application service for Commerce operating diagnosis workflows."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

from icore_agent.domain.agent.loop import ModelClient
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import UserInput, UserInputType, UserMessageItem
from icore_agent.domain.agent.tool import ToolChoice
from icore_agent.domain.commerce import CommerceDiagnosisReport
from icore_agent.domain.identifiers import uuid7

from .agent_profile import commerce_diagnosis_profile

LOW_MARGIN_THRESHOLD = Decimal("0.20")
EXPECTED_REPORT_TYPES = ("ads", "inventory", "logistics", "sales")
COMMERCE_AGENT_SYSTEM_PROMPT = (
    "You are the Commerce OS diagnosis agent. Analyze only the evidence packet "
    "provided by the backend. Do not invent SKUs, files, metrics, or missing "
    "tables. Return one JSON object only with optional keys: report_summary, "
    "risks, tasks. Keep recommendations operational and explicit when data is "
    "missing."
)
SAMPLE_CSV = (
    "sku,product,orders,revenue,cost,inventory,daily_sales,supplier,lead_time_days\n"
    "TRVL-CABLE-3P,Travel cable pack,30,900,450,4,2,Shenzhen Brightline,10\n"
    "DESK-LAMP-MINI,Mini desk lamp,5,100,85,80,0.5,Guangzhou Northstar,15\n"
    "PACK-CUBE-SET,Packing cube set,60,600,540,100,1,Ningbo Packwell,30\n"
).encode()
HEADER_ALIASES = {
    "sku": "sku",
    "sku_id": "sku",
    "skuid": "sku",
    "product_sku": "sku",
    "productsku": "sku",
    "商品编号": "sku",
    "商品编码": "sku",
    "商品sku": "sku",
    "货号": "sku",
    "产品编号": "sku",
    "product": "product",
    "product_name": "product",
    "productname": "product",
    "name": "product",
    "title": "product",
    "campaign_name": "product",
    "campaignname": "product",
    "商品名称": "product",
    "产品名称": "product",
    "品名": "product",
    "orders": "orders",
    "order_count": "orders",
    "ordercount": "orders",
    "units_sold": "orders",
    "unitssold": "orders",
    "quantity": "orders",
    "qty": "orders",
    "销量": "orders",
    "订单量": "orders",
    "销售数量": "orders",
    "revenue": "revenue",
    "sales": "revenue",
    "sales_amount": "revenue",
    "salesamount": "revenue",
    "revenue_usd": "revenue",
    "revenueusd": "revenue",
    "amount": "revenue",
    "gmv": "revenue",
    "销售额": "revenue",
    "销售金额": "revenue",
    "收入": "revenue",
    "cost": "cost",
    "cogs": "cost",
    "landed_cost": "cost",
    "landedcost": "cost",
    "spend_usd": "cost",
    "spendusd": "cost",
    "ad_spend": "cost",
    "adspend": "cost",
    "advertising_spend": "cost",
    "advertisingspend": "cost",
    "marketing_spend": "cost",
    "marketingspend": "cost",
    "成本": "cost",
    "商品成本": "cost",
    "采购成本": "cost",
    "inventory": "inventory",
    "inventory_qty": "inventory",
    "inventoryqty": "inventory",
    "current_stock": "inventory",
    "currentstock": "inventory",
    "stock": "inventory",
    "stock_qty": "inventory",
    "stockqty": "inventory",
    "on_hand": "inventory",
    "onhand": "inventory",
    "库存": "inventory",
    "库存数量": "inventory",
    "现有库存": "inventory",
    "daily_sales": "daily_sales",
    "dailysales": "daily_sales",
    "daily_sales_avg": "daily_sales",
    "dailysalesavg": "daily_sales",
    "avg_daily_sales": "daily_sales",
    "avgdailysales": "daily_sales",
    "daily_units_sold": "daily_sales",
    "dailyunitssold": "daily_sales",
    "日均销量": "daily_sales",
    "日销量": "daily_sales",
    "平均日销量": "daily_sales",
    "supplier": "supplier",
    "vendor": "supplier",
    "factory": "supplier",
    "供应商": "supplier",
    "厂商": "supplier",
    "工厂": "supplier",
    "lead_time_days": "lead_time_days",
    "leadtimedays": "lead_time_days",
    "lead_time": "lead_time_days",
    "leadtime": "lead_time_days",
    "交期": "lead_time_days",
    "交期天数": "lead_time_days",
    "供应商交期": "lead_time_days",
    "补货周期": "lead_time_days",
}


@dataclass(frozen=True)
class CommerceRow:
    """Normalized row used by deterministic Commerce diagnostics."""

    sku: str
    has_sku: bool
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


@dataclass(frozen=True)
class ParsedCommerceReport:
    """Parsed uploaded Commerce CSV with report-level metadata."""

    file_uuid: str
    filename: str
    report_type: str
    rows: list[CommerceRow]


class CommerceDiagnosisService:
    """Generate Commerce operating diagnoses from uploaded CSV files."""

    def __init__(
        self,
        *,
        file_service: Any,
        model_client_factory: Callable[..., ModelClient] | None = None,
    ) -> None:
        """Create the service with a user-owned file asset reader."""
        self._file_service = file_service
        self._model_client_factory = model_client_factory

    def create_diagnosis(
        self,
        *,
        user_id: str,
        file_uuid: str | None = None,
        file_uuids: list[str] | None = None,
        locale: str = "zh-CN",
    ) -> CommerceDiagnosisReport:
        """Create a synchronous V1 diagnosis from uploaded CSV files."""
        requested_file_uuids = _requested_file_uuids(
            file_uuid=file_uuid,
            file_uuids=file_uuids,
        )
        if len(requested_file_uuids) > 1:
            return self.create_diagnosis_for_files(
                user_id=user_id,
                file_uuids=requested_file_uuids,
                locale=locale,
            )
        file_uuid = requested_file_uuids[0]
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

    def create_diagnosis_for_files(
        self,
        *,
        user_id: str,
        file_uuids: list[str],
        locale: str = "zh-CN",
    ) -> CommerceDiagnosisReport:
        """Create one diagnosis from every available uploaded CSV file."""
        reports: list[ParsedCommerceReport] = []
        for file_uuid in _requested_file_uuids(file_uuids=file_uuids):
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
            reports.append(ParsedCommerceReport(
                file_uuid=file_uuid,
                filename=asset.original_filename,
                report_type=_detect_report_type(asset.original_filename, rows),
                rows=rows,
            ))
        rows = [row for report in reports for row in report.rows]
        return _build_report(
            rows,
            source_file=_combined_source_file(reports),
            locale=locale,
            metric_rows=_metric_rows_for_reports(reports),
        )

    async def create_agent_diagnosis(
        self,
        *,
        user_id: str,
        file_uuids: list[str],
        locale: str = "zh-CN",
    ) -> CommerceDiagnosisReport:
        """Create a Commerce diagnosis reviewed by the configured model agent."""
        baseline = self.create_diagnosis_for_files(
            user_id=user_id,
            file_uuids=file_uuids,
            locale=locale,
        )
        if self._model_client_factory is None:
            return _report_with_source_metadata(
                baseline,
                {"analysis_mode": "deterministic"},
            )
        try:
            model_client = self._model_client_factory(
                session_id=f"commerce:{baseline.diagnosis_id}",
                user_id=user_id,
            )
            result = await model_client.sample(
                _build_agent_prompt_envelope(baseline, locale=locale)
            )
            return _apply_agent_review(
                baseline,
                result.assistant_item.text,
                model=result.model,
                provider=result.provider,
            )
        except Exception as exc:
            return _report_with_source_metadata(
                baseline,
                {
                    "analysis_mode": "deterministic_fallback",
                    "agent_error": type(exc).__name__,
                },
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
    metric_rows: list[CommerceRow] | None = None,
) -> CommerceDiagnosisReport:
    """Build a Commerce diagnosis report from normalized CSV rows."""
    metrics = _summarize_metrics(metric_rows or rows)
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
        report_summary=_build_summary(
            metrics,
            risks,
            source_file=source_file,
            locale=locale,
        ),
    )


def _build_agent_prompt_envelope(
    report: CommerceDiagnosisReport,
    *,
    locale: str,
) -> PromptEnvelope:
    """Build the model prompt for Commerce evidence review."""
    evidence = _commerce_evidence_packet(report)
    return PromptEnvelope(
        base_instructions=COMMERCE_AGENT_SYSTEM_PROMPT,
        current_user_item=UserMessageItem(content=[
            UserInput(
                type=UserInputType.TEXT,
                text=(
                    "Review this Commerce diagnosis evidence packet and return "
                    f"JSON in locale {locale}.\n"
                    f"{json.dumps(evidence, ensure_ascii=False)}"
                ),
            )
        ]),
        tools=[],
        tool_choice=ToolChoice.NONE,
    )


def _commerce_evidence_packet(report: CommerceDiagnosisReport) -> dict[str, Any]:
    """Return structured evidence sent to the Commerce diagnosis agent."""
    return {
        "source_file": report.source_file,
        "metrics": report.metrics,
        "risks": report.risks[:20],
        "tasks": report.tasks[:20],
        "baseline_summary": report.report_summary,
        "rules": {
            "must_not_invent_skus": True,
            "must_state_missing_sources": bool(
                report.source_file.get("missing_sources")
            ),
        },
    }


def _apply_agent_review(
    report: CommerceDiagnosisReport,
    text: str,
    *,
    model: str | None,
    provider: str | None,
) -> CommerceDiagnosisReport:
    """Apply a validated model JSON review to the deterministic report."""
    payload = _parse_agent_json(text)
    summary = str(payload.get("report_summary") or "").strip()
    risks = payload.get("risks")
    tasks = payload.get("tasks")
    return CommerceDiagnosisReport(
        diagnosis_id=report.diagnosis_id,
        agent_profile=report.agent_profile,
        source_file={
            **report.source_file,
            "analysis_mode": "agent",
            "agent_model": model or "",
            "agent_provider": provider or "",
        },
        metrics=report.metrics,
        risks=_dict_list_or_default(risks, report.risks),
        tasks=_dict_list_or_default(tasks, report.tasks),
        report_summary=summary or report.report_summary,
    )


def _parse_agent_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from the Commerce agent response."""
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Commerce agent returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Commerce agent response must be a JSON object")
    return payload


def _dict_list_or_default(value: Any, default: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a JSON-object list from model output or keep the baseline list."""
    if not isinstance(value, list):
        return default
    items = [item for item in value if isinstance(item, dict)]
    return items or default


def _report_with_source_metadata(
    report: CommerceDiagnosisReport,
    metadata: dict[str, Any],
) -> CommerceDiagnosisReport:
    """Return a copy of a diagnosis report with additional source metadata."""
    return CommerceDiagnosisReport(
        diagnosis_id=report.diagnosis_id,
        agent_profile=report.agent_profile,
        source_file={**report.source_file, **metadata},
        metrics=report.metrics,
        risks=report.risks,
        tasks=report.tasks,
        report_summary=report.report_summary,
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
    raw_sku = _text(normalized, "sku")
    sku = raw_sku or _row_identifier(normalized, line_no)
    revenue = _decimal(normalized, "revenue")
    cost = _decimal(normalized, "cost")
    inventory = _decimal(normalized, "inventory")
    daily_sales = _decimal(normalized, "daily_sales")
    return CommerceRow(
        sku=sku,
        has_sku=bool(raw_sku),
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
    product_skus = {row.sku for row in rows if row.has_sku}
    margin_rate = (
        (total_revenue - total_cost) / total_revenue
        if total_revenue > 0
        else Decimal("0")
    )
    return {
        "sku_count": len(product_skus) if product_skus else len(rows),
        "row_count": len(rows),
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
        if row.revenue > 0 and row.gross_margin_rate < LOW_MARGIN_THRESHOLD:
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
    source_file: dict[str, Any],
    locale: str,
) -> str:
    """Build a concise human-readable diagnosis summary."""
    primary = risks[0] if risks else None
    missing_copy = _missing_source_copy(source_file)
    if locale == "zh-CN":
        if primary:
            missing_suffix = f"，缺少 {missing_copy} 数据" if missing_copy else ""
            return (
                f"本次诊断覆盖 {metrics['sku_count']} 个 SKU，销售额 "
                f"{metrics['total_revenue']}，发现首要风险 {primary['sku']} "
                f"({primary['type']}){missing_suffix}，建议优先处理。"
            )
        missing_suffix = f"，缺少 {missing_copy} 数据" if missing_copy else ""
        return (
            f"本次诊断覆盖 {metrics['sku_count']} 个 SKU{missing_suffix}，"
            "暂未发现高优先级运营风险。"
        )
    if primary:
        missing_suffix = f" Missing {missing_copy} data." if missing_copy else ""
        return (
            f"Diagnosis covers {metrics['sku_count']} SKUs. The first priority is "
            f"{primary['sku']} ({primary['type']}).{missing_suffix}"
        )
    missing_suffix = f" Missing {missing_copy} data." if missing_copy else ""
    return (
        f"Diagnosis covers {metrics['sku_count']} SKUs with no high-priority risk."
        f"{missing_suffix}"
    )


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


def _row_identifier(row: dict[str, str], line_no: int) -> str:
    """Return a stable identifier for non-SKU operating report rows."""
    for key in ("campaign_id", "shipment_id", "po_number", "product"):
        value = _text(row, key)
        if value:
            return value
    return f"row-{line_no}"


def _requested_file_uuids(
    *,
    file_uuid: str | None = None,
    file_uuids: list[str] | None = None,
) -> list[str]:
    """Return a de-duplicated upload UUID list for diagnosis."""
    raw_values = list(file_uuids or [])
    if file_uuid:
        raw_values.append(file_uuid)
    requested: list[str] = []
    for raw_value in raw_values:
        value = str(raw_value or "").strip()
        if value and value not in requested:
            requested.append(value)
    if not requested:
        raise ValueError("At least one CSV file is required")
    return requested


def _combined_source_file(reports: list[ParsedCommerceReport]) -> dict[str, Any]:
    """Build public source metadata for a multi-report diagnosis."""
    available_sources = [
        report_type
        for report_type in EXPECTED_REPORT_TYPES
        if any(report.report_type == report_type for report in reports)
    ]
    missing_sources = [
        report_type
        for report_type in EXPECTED_REPORT_TYPES
        if report_type not in available_sources
    ]
    first = reports[0]
    filename = first.filename if len(
        reports) == 1 else f"{first.filename} + {len(reports) - 1}"
    return {
        "file_uuid": first.file_uuid,
        "file_uuids": [report.file_uuid for report in reports],
        "filename": filename,
        "row_count": sum(len(report.rows) for report in reports),
        "files": [
            {
                "file_uuid": report.file_uuid,
                "filename": report.filename,
                "row_count": len(report.rows),
                "report_type": report.report_type,
            }
            for report in reports
        ],
        "available_sources": available_sources,
        "missing_sources": missing_sources,
    }


def _detect_report_type(filename: str, rows: list[CommerceRow]) -> str:
    """Infer a Commerce report type from filename and normalized row signals."""
    lowered = filename.lower()
    if "ads" in lowered or "traffic" in lowered or "campaign" in lowered:
        return "ads"
    if "inventory" in lowered or "replenishment" in lowered or "stock" in lowered:
        return "inventory"
    if "logistics" in lowered or "shipment" in lowered or "supply" in lowered:
        return "logistics"
    if "sales" in lowered or "order" in lowered:
        return "sales"
    if any(row.revenue > 0 and not row.has_sku for row in rows):
        return "ads"
    if any(row.inventory > 0 and row.daily_sales > 0 for row in rows):
        return "inventory"
    if any(row.orders > 0 and row.revenue > 0 for row in rows):
        return "sales"
    return "unknown"


def _metric_rows_for_reports(reports: list[ParsedCommerceReport]) -> list[CommerceRow]:
    """Choose rows for top-level operating metrics without double-counting."""
    sales_rows = [
        row
        for report in reports
        if report.report_type == "sales"
        for row in report.rows
    ]
    if sales_rows:
        return sales_rows
    return [row for report in reports for row in report.rows]


def _missing_source_copy(source_file: dict[str, Any]) -> str:
    """Return display copy for missing multi-report source types."""
    missing_sources = source_file.get("missing_sources")
    if not isinstance(missing_sources, list) or not missing_sources:
        return ""
    return "、".join(str(source) for source in missing_sources)


def _normalize_key(key: str | None) -> str:
    """Normalize CSV headers into snake-like lookup keys."""
    normalized = (
        str(key or "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )
    compact = normalized.replace("_", "")
    return HEADER_ALIASES.get(
        normalized,
        HEADER_ALIASES.get(compact, normalized),
    )


def _float(value: Decimal, *, places: int = 2) -> float:
    """Return a rounded JSON-friendly float."""
    quant = Decimal("1").scaleb(-places)
    return float(value.quantize(quant))


def _risk_sort_key(risk: dict[str, Any]) -> tuple[int, str]:
    """Sort high-severity risks first while keeping SKU order stable."""
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return severity_rank.get(str(risk.get("severity")), 9), str(risk.get("sku"))
