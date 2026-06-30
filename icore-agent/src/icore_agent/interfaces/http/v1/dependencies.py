"""Dependency providers shared across API routers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from icore_agent.application.account import AccountService
from icore_agent.application.billing import BillingService
from icore_agent.application.agent import (
    AgentRuntime,
    AgentSessionService,
    AgentTurnService,
)
from icore_agent.application.files import FileAssetService
from icore_agent.application.pi_workspaces import PiWorkspaceService
from icore_agent.application.knowledge import KnowledgeService
from icore_agent.application.memory import UserMemoryService
from icore_agent.application.usage import UsageService
from icore_agent.application.workspace import WorkspaceMetadataService
from icore_agent.config import settings
from icore_agent.domain.user import AuthenticatedUser
from icore_agent.infrastructure.control_plane import (
    ControlPlaneLeadRepository,
    ControlPlaneVerificationRepository,
)
from icore_agent.infrastructure.control_plane.json_store import control_plane_store
from icore_agent.infrastructure.agent.chat_completions import (
    create_chat_completions_model_client,
)
from icore_agent.infrastructure.agent.runtime import RedisAgentRunStore
from icore_agent.infrastructure.persistence.files import SqlAlchemyFileRepository
from icore_agent.infrastructure.persistence.pi_workspaces import (
    SqlAlchemyPiWorkspaceRepository,
)
from icore_agent.infrastructure.memory.conversation import memory
from icore_agent.infrastructure.memory.chroma_store import (
    add_documents,
    get_collection,
    list_documents,
)
from icore_agent.infrastructure.persistence.memory import SqlAlchemyUserMemoryRepository
from icore_agent.infrastructure.persistence.users.postgres_repositories import (
    PostgresBillingRepository,
    PostgresBillingSummaryRepository,
    PostgresIdentityRepository,
    PostgresProjectRepository,
    PostgresRegistrationRepository,
    PostgresTeamRepository,
    PostgresUsageRepository,
)
from icore_agent.infrastructure.storage import StorageServiceClient

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
user_memory_repository = SqlAlchemyUserMemoryRepository()
user_memory_service = UserMemoryService(user_memory_repository)
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
agent_session_service = AgentSessionService()
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
pi_workspace_service = PiWorkspaceService(
    repository=SqlAlchemyPiWorkspaceRepository(),
    storage_client=StorageServiceClient(
        base_url=settings.storage_service_url,
        token=settings.storage_service_token,
        timeout=settings.storage_service_timeout,
    ),
    bucket=settings.pi_workspace_bucket,
    default_expires_in=settings.pi_workspace_upload_url_expires_in,
    max_size_mb=settings.pi_workspace_max_size_mb,
    max_files=settings.pi_workspace_max_files,
)
agent_run_store = RedisAgentRunStore(
    redis_url=settings.redis_url,
    lock_ttl_seconds=settings.agent_runtime_lock_ttl_seconds,
    state_ttl_seconds=settings.agent_runtime_state_ttl_seconds,
)
agent_runtime = AgentRuntime(run_store=agent_run_store)


def get_account_service() -> AccountService:
    """Return the singleton account service used by HTTP handlers."""
    return account_service


def get_billing_service() -> BillingService:
    """Return the singleton billing service used by HTTP handlers."""
    return billing_service


def get_usage_service() -> UsageService:
    """Return the singleton usage service used by infrastructure and app wiring."""
    return usage_service


def get_user_memory_service() -> UserMemoryService:
    """Return the singleton user memory service used by chat workflows."""
    return user_memory_service


def get_knowledge_service() -> KnowledgeService:
    """Return the singleton knowledge service used by HTTP handlers."""
    return knowledge_service


def get_file_asset_service() -> FileAssetService:
    """Return the singleton file asset service used by HTTP handlers."""
    return file_asset_service


def get_pi_workspace_service() -> PiWorkspaceService:
    """Return the singleton Pi workspace service used by HTTP handlers."""
    return pi_workspace_service


def get_agent_session_service() -> AgentSessionService:
    """Return the singleton agent session service used by agent handlers."""
    return agent_session_service


def get_agent_turn_service() -> AgentTurnService:
    """Return an application service for one HTTP agent turn.

    usage_service is injected so that every agent turn enforces token quota
    before invoking the LLM.  The LiteLLM success callback in main.py then
    records actual usage and decrements the quota counter after the reply.
    """
    return AgentTurnService(
        agent_session=agent_session_service,
        file_service=file_asset_service,
        conversation_memory=memory,
        model_client_factory=create_chat_completions_model_client,
        usage_service=usage_service,
        user_memory_service=user_memory_service,
        pi_workspace_service=pi_workspace_service,
        agent_runtime=agent_runtime,
    )


def get_current_user(
    authorization: str = Header(default=""),
    service: AccountService = Depends(get_account_service),
) -> AuthenticatedUser:
    """Resolve the authenticated user from the bearer token header."""
    try:
        return AuthenticatedUser.from_profile(
            service.get_current_user(authorization)
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
