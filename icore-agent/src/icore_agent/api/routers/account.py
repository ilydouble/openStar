"""Account, plan, and usage endpoints for the first productized release."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from ...application.account import AccountService
from ..dependencies import get_account_service

router = APIRouter()


class SendVerificationCodeRequest(BaseModel):
    email: EmailStr


class SendVerificationCodeResponse(BaseModel):
    success: bool
    message: str


class TrialRegistrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)


class TrialRegistrationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class EmailLoginRequest(BaseModel):
    """邮箱 + 验证码登录（已注册用户）"""
    email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)


class EmailLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ByokRequest(BaseModel):
    api_key: str = ""
    api_base: str = ""
    model: str = ""


class ProjectSyncRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=120)
    project_title: str = Field(..., min_length=1, max_length=200)
    scenario_id: str = Field(default="", max_length=80)
    session_id: str = Field(..., min_length=1, max_length=120)
    session_title: str = Field(..., min_length=1, max_length=200)
    session_subtitle: str = Field(default="", max_length=500)
    attachment_count: int = Field(default=0, ge=0, le=500)


class OrganizationRenameRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=120)


class TeamMemberRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    role: str = Field(default="viewer", max_length=40)


class KnowledgeScopeRequest(BaseModel):
    scope: str = Field(..., pattern="^(private|organization)$")


class LeadCaptureRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(default="", max_length=160)
    team_size: str = Field(default="", max_length=80)
    use_case: str = Field(default="", max_length=2000)
    needs_byok: bool = False
    needs_private_deploy: bool = False
    source: str = Field(default="landing", max_length=80)
    intent: str = Field(default="demo", pattern="^(demo|enterprise|upgrade-team|upgrade-enterprise)$")


def get_current_user(
    authorization: str = Header(default=""),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Resolve the current user through the account application service."""
    try:
        return service.get_current_user(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/send-verification-code", response_model=SendVerificationCodeResponse)
async def send_verification_code(
    req: SendVerificationCodeRequest,
    request: Request,
    service: AccountService = Depends(get_account_service),
) -> SendVerificationCodeResponse:
    """发送邮箱验证码（同一 IP 24 小时内最多发送 3 次）"""
    client_ip = request.client.host if request.client else "unknown"

    success, message = service.send_verification_code(req.email, client_ip)
    if not success:
        raise HTTPException(status_code=429, detail=message)

    return SendVerificationCodeResponse(success=True, message=message)


@router.post("/login", response_model=EmailLoginResponse)
async def email_login(
    req: EmailLoginRequest,
    service: AccountService = Depends(get_account_service),
) -> EmailLoginResponse:
    """邮箱 + 验证码登录（已注册用户，无 IP 限流）"""
    try:
        user, token = service.login_with_email_code(req.email, req.verification_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EmailLoginResponse(access_token=token, user=user)


@router.post("/register-trial", response_model=TrialRegistrationResponse)
async def register_trial(
    req: TrialRegistrationRequest,
    request: Request,
    service: AccountService = Depends(get_account_service),
) -> TrialRegistrationResponse:
    """注册试用账号（需要邮箱验证码 + IP 限流：同一 IP 24 小时内只能注册 1 次）"""
    client_ip = request.client.host if request.client else "unknown"

    try:
        user, token = service.register_trial(
            name=req.name,
            email=req.email,
            verification_code=req.verification_code,
            client_ip=client_ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return TrialRegistrationResponse(access_token=token, user=user)


@router.post("/leads")
async def capture_lead(
    req: LeadCaptureRequest,
    service: AccountService = Depends(get_account_service),
) -> dict:
    lead = service.capture_lead(
        name=req.name,
        email=req.email,
        company=req.company,
        team_size=req.team_size,
        use_case=req.use_case,
        needs_byok=req.needs_byok,
        needs_private_deploy=req.needs_private_deploy,
        source=req.source,
        intent=req.intent,
    )
    return {"lead": lead}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)) -> dict:
    return user


@router.get("/usage/summary")
async def get_usage_summary(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    return service.get_usage_summary(user["id"])


@router.get("/admin/overview")
async def get_admin_overview(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    try:
        return service.get_admin_overview(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/billing/plan")
async def get_plan(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    return service.get_plan(user["id"])


@router.post("/billing/byok")
async def update_byok(
    req: ByokRequest,
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    return service.update_byok(user["id"], req.api_key, req.api_base, req.model)


@router.post("/projects/sync")
async def sync_project(
    req: ProjectSyncRequest,
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    project = service.sync_project(
        user_id=user["id"],
        project_id=req.project_id,
        project_title=req.project_title,
        scenario_id=req.scenario_id,
        session_id=req.session_id,
        session_title=req.session_title,
        session_subtitle=req.session_subtitle,
        attachment_count=req.attachment_count,
    )
    return {"project": project}


@router.get("/projects")
async def list_projects(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    return service.list_projects(user["id"])


@router.get("/team")
async def get_team(
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    return service.get_team(user["id"])


@router.post("/team/rename")
async def rename_team(
    req: OrganizationRenameRequest,
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    return service.rename_team(user["id"], req.organization_name)


@router.post("/team/members")
async def add_team_member(
    req: TeamMemberRequest,
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    member = service.add_team_member(
        user["id"], name=req.name, email=req.email, role=req.role
    )
    return {"member": member}


@router.post("/team/knowledge-scope")
async def update_team_knowledge_scope(
    req: KnowledgeScopeRequest,
    user: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    return service.update_team_knowledge_scope(user["id"], req.scope)
