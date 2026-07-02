"""Domain model for Commerce operating diagnosis reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


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


class CommerceDiagnosisRepository(Protocol):
    """Persistence contract for Commerce diagnosis report snapshots."""

    def save(
        self,
        user_id: str,
        report: CommerceDiagnosisReport,
    ) -> CommerceDiagnosisReport:
        """Persist one diagnosis report snapshot for a user."""
        ...

    def get_latest_for_user(self, user_id: str) -> CommerceDiagnosisReport | None:
        """Return the most recent diagnosis report for a user."""
        ...
