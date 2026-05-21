"""Dependency providers shared across API routers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from icore_agent.application.account import AccountService
from icore_agent.application.billing import BillingService
from icore_agent.application.files import FileAssetService
from icore_agent.application.knowledge import KnowledgeService
from icore_agent.application.usage import UsageService
from icore_agent.config import settings
from icore_agent.infrastructure.control_plane import (
    ControlPlaneLeadRepository,
    ControlPlaneVerificationRepository,
)
from icore_agent.infrastructure.control_plane.json_store import control_plane_store
from icore_agent.infrastructure.memory.chroma_store import (
    add_documents,
    get_collection,
    list_documents,
)
from icore_agent.infrastructure.persistence.users.postgres_repositories import (
    PostgresBillingRepository,
    PostgresBillingSummaryRepository,
    PostgresIdentityRepository,
    PostgresProjectRepository,
    PostgresRegistrationRepository,
    PostgresTeamRepository,
    PostgresUsageRepository,
)
from icore_agent.infrastructure.persistence.files import SqlAlchemyFileRepository
from icore_agent.infrastructure.storage import StorageServiceClient

from .users import serialize_user_profile

identity_repository = PostgresIdentityRepository(control_plane_store)
verification_repository = ControlPlaneVerificationRepository(
    control_plane_store)
registration_repository = PostgresRegistrationRepository(control_plane_store)
lead_repository = ControlPlaneLeadRepository(control_plane_store)
team_repository = PostgresTeamRepository(
    control_plane_store, identity_repository)
project_repository = PostgresProjectRepository(
    control_plane_store, identity_repository)
billing_summary_repository = PostgresBillingSummaryRepository(
    control_plane_store)
usage_store = PostgresUsageRepository(control_plane_store)
usage_service = UsageService(usage_store)
billing_repository = PostgresBillingRepository(control_plane_store)

account_service = AccountService(
    identity_repository=identity_repository,
    verification_repository=verification_repository,
    registration_repository=registration_repository,
    lead_repository=lead_repository,
    team_repository=team_repository,
    project_repository=project_repository,
    billing_summary_repository=billing_summary_repository,
    usage_service=usage_service,
)
billing_service = BillingService(
    billing_repository,
    settings.icore_base_url or "http://localhost:11000",
)
knowledge_service = KnowledgeService(
    add_documents=add_documents,
    list_documents=list_documents,
    get_collection=get_collection,
    rag_chunk_size=settings.rag_chunk_size,
    rag_chunk_overlap=settings.rag_chunk_overlap,
    file_size_limit_mb=settings.file_ops_max_size_mb,
)
file_asset_service = FileAssetService(
    repository=SqlAlchemyFileRepository(),
    storage_client=StorageServiceClient(
        base_url=settings.storage_service_url,
        token=settings.storage_service_token,
        timeout=settings.storage_service_timeout,
    ),
    bucket=settings.file_storage_bucket,
    default_expires_in=settings.file_upload_url_expires_in,
)


def get_account_service() -> AccountService:
    """Return the singleton account service used by HTTP handlers."""
    return account_service


def get_billing_service() -> BillingService:
    """Return the singleton billing service used by HTTP handlers."""
    return billing_service


def get_usage_service() -> UsageService:
    """Return the singleton usage service used by infrastructure and app wiring."""
    return usage_service


def get_knowledge_service() -> KnowledgeService:
    """Return the singleton knowledge service used by HTTP handlers."""
    return knowledge_service


def get_file_asset_service() -> FileAssetService:
    """Return the singleton file asset service used by HTTP handlers."""
    return file_asset_service


def get_current_user(
    authorization: str = Header(default=""),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Resolve the authenticated user from the bearer token header."""
    try:
        return serialize_user_profile(service.get_current_user(authorization))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
