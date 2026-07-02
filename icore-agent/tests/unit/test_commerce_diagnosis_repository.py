from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from icore_agent.domain.commerce import CommerceDiagnosisReport
from icore_agent.infrastructure.persistence.commerce import (
    SqlAlchemyCommerceDiagnosisRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.models import Base


def test_commerce_diagnosis_repository_saves_and_loads_latest_report() -> None:
    """Commerce diagnosis snapshots should be persisted per owning user."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    @contextmanager
    def session_scope():
        """Open one transactional SQLAlchemy session for the test repository."""
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    repo = SqlAlchemyCommerceDiagnosisRepository(session_scope)
    older = _report("diagnosis-old", revenue=100)
    newer = _report("diagnosis-new", revenue=200)

    repo.save("user-one", older)
    repo.save("user-two", _report("diagnosis-other", revenue=999))
    repo.save("user-one", newer)

    loaded = repo.get_latest_for_user("user-one")

    assert loaded is not None
    assert loaded.diagnosis_id == "diagnosis-new"
    assert loaded.metrics["total_revenue"] == 200
    assert loaded.source_file["file_uuids"] == ["file-1", "file-2"]
    assert loaded.tasks[0]["type"] == "replenishment"
    assert repo.get_latest_for_user("missing-user") is None


def _report(diagnosis_id: str, *, revenue: int) -> CommerceDiagnosisReport:
    """Build a deterministic diagnosis report for repository tests."""
    return CommerceDiagnosisReport(
        diagnosis_id=diagnosis_id,
        agent_profile="commerce_diagnosis_v1",
        source_file={
            "file_uuids": ["file-1", "file-2"],
            "available_sources": ["sales", "inventory"],
            "missing_sources": ["ads", "logistics"],
            "analysis_mode": "agent",
        },
        metrics={"sku_count": 2, "total_revenue": revenue},
        risks=[{"type": "stockout", "sku": "SKU-A"}],
        tasks=[{"type": "replenishment", "sku": "SKU-A"}],
        report_summary=f"Revenue {revenue}",
    )
