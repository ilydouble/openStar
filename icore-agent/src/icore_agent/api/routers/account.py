"""Account, plan, and usage endpoints for the first productized release."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ...control_plane import control_plane_store

router = APIRouter()


class TrialRegistrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr


class TrialRegistrationResponse(BaseModel):
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


def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:].strip()
    user = control_plane_store.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@router.post("/register-trial", response_model=TrialRegistrationResponse)
async def register_trial(req: TrialRegistrationRequest) -> TrialRegistrationResponse:
    user, token = control_plane_store.register_trial(req.name, req.email)
    return TrialRegistrationResponse(access_token=token, user=user)


@router.post("/leads")
async def capture_lead(req: LeadCaptureRequest) -> dict:
    lead = control_plane_store.create_lead(
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
async def get_usage_summary(user: dict = Depends(get_current_user)) -> dict:
    return control_plane_store.usage_summary(user["id"])


@router.get("/admin/overview")
async def get_admin_overview(user: dict = Depends(get_current_user)) -> dict:
    # 只允许拥有 owner 或 admin 角色的用户访问运营总览
    roles = user.get("roles") or []
    if "owner" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Only users with 'owner' or 'admin' role can access this endpoint."
        )
    return control_plane_store.admin_overview()


@router.get("/billing/plan")
async def get_plan(user: dict = Depends(get_current_user)) -> dict:
    return control_plane_store.get_plan_summary(user["id"])


@router.post("/billing/byok")
async def update_byok(req: ByokRequest, user: dict = Depends(get_current_user)) -> dict:
    byok = control_plane_store.update_byok(user["id"], req.api_key, req.api_base, req.model)
    return byok


@router.post("/projects/sync")
async def sync_project(req: ProjectSyncRequest, user: dict = Depends(get_current_user)) -> dict:
    project = control_plane_store.sync_project_session(
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
async def list_projects(user: dict = Depends(get_current_user)) -> dict:
    return control_plane_store.list_projects(user["id"])


@router.get("/team")
async def get_team(user: dict = Depends(get_current_user)) -> dict:
    return control_plane_store.get_team_profile(user["id"])


@router.post("/team/rename")
async def rename_team(req: OrganizationRenameRequest, user: dict = Depends(get_current_user)) -> dict:
    return control_plane_store.rename_organization(user["id"], req.organization_name)


@router.post("/team/members")
async def add_team_member(req: TeamMemberRequest, user: dict = Depends(get_current_user)) -> dict:
    member = control_plane_store.add_team_member(
        user["id"], name=req.name, email=req.email, role=req.role
    )
    return {"member": member}


@router.post("/team/knowledge-scope")
async def update_team_knowledge_scope(req: KnowledgeScopeRequest, user: dict = Depends(get_current_user)) -> dict:
    return control_plane_store.update_knowledge_scope(user["id"], req.scope)
