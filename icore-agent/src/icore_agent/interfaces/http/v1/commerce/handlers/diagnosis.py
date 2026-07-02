"""HTTP handlers for Commerce diagnosis workflows."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from icore_agent.application.account import AccountService
from icore_agent.application.commerce import CommerceDiagnosisService
from icore_agent.application.files import FileAssetNotFoundError
from icore_agent.domain.commerce import CommerceDiagnosisReport
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import account_service, file_asset_service
from ..schemas import (
    CommerceDiagnosisRequest,
    CommerceDiagnosisResponse,
    CommerceSampleDiagnosisRequest,
)


async def get_commerce_current_user(
    authorization: str = Header(default=""),
) -> AuthenticatedUser:
    """Resolve the current user for Commerce routes."""
    try:
        service: AccountService = account_service
        return AuthenticatedUser.from_profile(
            service.get_current_user(authorization)
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def get_commerce_diagnosis_service() -> CommerceDiagnosisService:
    """Return the Commerce diagnosis service."""
    return CommerceDiagnosisService(file_service=file_asset_service)


async def create_commerce_diagnosis(
    payload: CommerceDiagnosisRequest,
    user: AuthenticatedUser = Depends(get_commerce_current_user),
    service: CommerceDiagnosisService = Depends(
        get_commerce_diagnosis_service),
) -> CommerceDiagnosisResponse:
    """Create a Commerce diagnosis report for an uploaded CSV file."""
    try:
        file_uuids = payload.normalized_file_uuids
        if len(file_uuids) > 1:
            report = service.create_diagnosis_for_files(
                user_id=user.public_id,
                file_uuids=file_uuids,
                locale=payload.locale,
            )
        else:
            report = service.create_diagnosis(
                user_id=user.public_id,
                file_uuid=file_uuids[0],
                locale=payload.locale,
            )
    except FileAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_report(report)


async def create_sample_commerce_diagnosis(
    payload: CommerceSampleDiagnosisRequest,
    _user: AuthenticatedUser = Depends(get_commerce_current_user),
    service: CommerceDiagnosisService = Depends(
        get_commerce_diagnosis_service),
) -> CommerceDiagnosisResponse:
    """Create a Commerce sample diagnosis without requiring an uploaded CSV."""
    report = service.create_sample_diagnosis(locale=payload.locale)
    return _serialize_report(report)


def _serialize_report(report: CommerceDiagnosisReport) -> CommerceDiagnosisResponse:
    """Serialize a domain report into the public HTTP schema."""
    return CommerceDiagnosisResponse(
        diagnosis_id=report.diagnosis_id,
        agent_profile=report.agent_profile,
        source_file=report.source_file,
        metrics=report.metrics,
        risks=report.risks,
        tasks=report.tasks,
        report_summary=report.report_summary,
    )
