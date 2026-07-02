"""Commerce agent profile definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommerceAgentProfile:
    """Describe one Commerce agent's workflow and tool surface."""

    id: str
    workflow_steps: tuple[str, ...]
    tool_names: tuple[str, ...]


def commerce_diagnosis_profile() -> CommerceAgentProfile:
    """Return the V1 Commerce operating diagnosis agent profile."""
    return CommerceAgentProfile(
        id="commerce_diagnosis_v1",
        workflow_steps=(
            "load_uploaded_csv",
            "profile_operating_metrics",
            "detect_inventory_and_margin_risks",
            "generate_report_and_tasks",
        ),
        tool_names=(
            "read_uploaded_file",
            "csv_profile",
            "sales_kpi_analyzer",
            "inventory_risk_analyzer",
        ),
    )
