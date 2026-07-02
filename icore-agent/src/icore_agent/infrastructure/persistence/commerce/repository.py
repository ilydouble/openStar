"""SQLAlchemy implementation of Commerce diagnosis persistence."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from icore_agent.application.usage.policy import current_timestamp
from icore_agent.domain.commerce import CommerceDiagnosisReport

from ..sqlalchemy.sync_session import sync_session_scope
from .models import CommerceDiagnosisRecord

SessionScope = Callable[[], AbstractContextManager[Session]]


class SqlAlchemyCommerceDiagnosisRepository:
    """Persist Commerce diagnosis report snapshots through SQLAlchemy."""

    def __init__(
        self,
        session_scope: SessionScope = sync_session_scope,
    ) -> None:
        """Create a repository using the provided session scope factory."""
        self._session_scope = session_scope

    def save(
        self,
        user_id: str,
        report: CommerceDiagnosisReport,
    ) -> CommerceDiagnosisReport:
        """Insert or update one diagnosis report snapshot."""
        with self._session_scope() as session:
            row = session.execute(
                select(CommerceDiagnosisRecord)
                .where(CommerceDiagnosisRecord.diagnosis_id == report.diagnosis_id)
            ).scalar_one_or_none()
            if row is None:
                row = CommerceDiagnosisRecord(
                    diagnosis_id=report.diagnosis_id,
                    user_id=user_id,
                    created_at=current_timestamp(),
                )
                session.add(row)
            _apply_report(row, report, user_id=user_id)
            session.flush()
            return _to_report(row)

    def get_latest_for_user(self, user_id: str) -> CommerceDiagnosisReport | None:
        """Return the newest persisted diagnosis report for a user."""
        with self._session_scope() as session:
            row = session.execute(
                select(CommerceDiagnosisRecord)
                .where(CommerceDiagnosisRecord.user_id == user_id)
                .order_by(
                    CommerceDiagnosisRecord.created_at.desc(),
                    CommerceDiagnosisRecord.id.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
            return _to_report(row) if row is not None else None


def _apply_report(
    row: CommerceDiagnosisRecord,
    report: CommerceDiagnosisReport,
    *,
    user_id: str,
) -> None:
    """Copy a domain diagnosis report onto an ORM row."""
    row.user_id = user_id
    row.agent_profile = report.agent_profile
    row.source_file = dict(report.source_file)
    row.metrics = dict(report.metrics)
    row.risks = list(report.risks)
    row.tasks = list(report.tasks)
    row.report_summary = report.report_summary


def _to_report(row: CommerceDiagnosisRecord) -> CommerceDiagnosisReport:
    """Convert an ORM row into a domain diagnosis report."""
    return CommerceDiagnosisReport(
        diagnosis_id=row.diagnosis_id,
        agent_profile=row.agent_profile,
        source_file={**dict(row.source_file or {}),
                     "created_at": row.created_at},
        metrics=dict(row.metrics or {}),
        risks=list(row.risks or []),
        tasks=list(row.tasks or []),
        report_summary=row.report_summary,
    )
