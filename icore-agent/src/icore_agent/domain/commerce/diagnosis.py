"""Domain model for Commerce operating diagnosis reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CommerceDiagnosisReport:
    """Represent one generated Commerce operating diagnosis."""

    diagnosis_id: str
    agent_profile: str
    source_file: dict[str, Any]
    metrics: dict[str, Any]
    risks: list[dict[str, Any]] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    report_summary: str = ""
