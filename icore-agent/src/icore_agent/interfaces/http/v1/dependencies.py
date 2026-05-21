"""Dependency providers shared across API routers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from icore_agent.application.account import AccountService
from icore_agent.application.billing import BillingService
from icore_agent.application.chat import ChatHistoryService
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
from icore_agent.application.workspace import WorkspaceMetadataService
from icore_agent.infrastructure.persistence.users.postgres_repositories import (
    PostgresBillingRepository,
    PostgresBillingSummaryRepository,
    PostgresIdentityRepository,
    PostgresProjectRepository,
    PostgresRegistrationRepository,
    PostgresTeamRepository,
    PostgresUsageRepository,
)

from .users import serialize_user_profile

workspace_metadata_service = WorkspaceMetadataService()
identity_repository = PostgresIdentityRepository(
    control_plane_store, workspace_metadata_service)
verification_repository = ControlPlaneVerificationRepository(
    control_plane_store)
registration_repository = PostgresRegistrationRepository(
    control_plane_store, workspace_metadata_service)
lead_repository = ControlPlaneLeadRepository(control_plane_store)
team_repository = PostgresTeamRepository(workspace_metadata_service)
project_repository = PostgresProjectRepository(workspace_metadata_service)
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
chat_history_service = ChatHistoryService()
knowledge_service = KnowledgeService(
    add_documents=add_documents,
    list_documents=list_documents,
    get_collection=get_collection,
    rag_chunk_size=settings.rag_chunk_size,
    rag_chunk_overlap=settings.rag_chunk_overlap,
    file_size_limit_mb=settings.file_ops_max_size_mb,
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


def get_chat_history_service() -> ChatHistoryService:
    """Return the singleton chat history service used by agent handlers."""
    return chat_history_service


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
