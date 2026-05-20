"""Dependency providers shared across API routers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from ..application.account import AccountService
from ..application.billing import BillingService
from ..application.knowledge import KnowledgeService
from ..application.usage import UsageService
from ..config import settings
from ..control_plane import control_plane_store
from ..infrastructure.control_plane import (
    ControlPlaneBillingRepository,
    ControlPlaneBillingSummaryRepository,
    ControlPlaneIdentityRepository,
    ControlPlaneLeadRepository,
    ControlPlaneProjectRepository,
    ControlPlaneRegistrationRepository,
    ControlPlaneTeamRepository,
    ControlPlaneUsageRepository,
    ControlPlaneVerificationRepository,
)
from ..memory.chroma_store import add_documents, get_collection, list_documents

identity_repository = ControlPlaneIdentityRepository(control_plane_store)
verification_repository = ControlPlaneVerificationRepository(control_plane_store)
registration_repository = ControlPlaneRegistrationRepository(control_plane_store)
lead_repository = ControlPlaneLeadRepository(control_plane_store)
team_repository = ControlPlaneTeamRepository(control_plane_store)
project_repository = ControlPlaneProjectRepository(control_plane_store)
billing_summary_repository = ControlPlaneBillingSummaryRepository(control_plane_store)
usage_repository = ControlPlaneUsageRepository(control_plane_store)
billing_repository = ControlPlaneBillingRepository(control_plane_store)

account_service = AccountService(
    identity_repository=identity_repository,
    verification_repository=verification_repository,
    registration_repository=registration_repository,
    lead_repository=lead_repository,
    team_repository=team_repository,
    project_repository=project_repository,
    billing_summary_repository=billing_summary_repository,
    usage_repository=usage_repository,
)
billing_service = BillingService(
    billing_repository,
    settings.icore_base_url or "http://localhost:8080",
)
usage_service = UsageService(usage_repository)
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


def get_current_user(
    authorization: str = Header(default=""),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Resolve the authenticated user from the bearer token header.

    When AUTH_ENABLED=false, returns the first user in the database as a fallback
    for local development without authentication.
    """
    # 如果认证已禁用，返回数据库中第一个用户（仅限本地开发）
    if not settings.auth_enabled:
        users = control_plane_store._load().get("users", {})
        if users:
            first_user_id = next(iter(users.keys()))
            user = control_plane_store.get_user_by_token("")  # 使用空 token 触发加载
            if not user:
                # 直接返回第一个用户
                user = users[first_user_id]
                # 确保有 organization
                control_plane_store._ensure_org_for_user(control_plane_store._load(), user)
            return user
        # 如果没有用户，返回一个虚拟的默认用户
        return {
            "id": "dev-user-id",
            "email": "dev@local.test",
            "name": "Development User",
            "plan": "free",
            "roles": ["owner"],
        }

    # 正常认证流程
    try:
        return service.get_current_user(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
