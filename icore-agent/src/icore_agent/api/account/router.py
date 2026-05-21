"""Account API router."""

from fastapi import APIRouter

from .handlers import (
    add_team_member,
    capture_lead,
    email_login,
    get_admin_overview,
    get_me,
    get_plan,
    get_team,
    get_usage_summary,
    list_projects,
    register_trial,
    rename_team,
    send_verification_code,
    sync_project,
    update_byok,
    update_team_knowledge_scope,
)
from .schemas import (
    EmailLoginResponse,
    SendVerificationCodeResponse,
    TrialRegistrationResponse,
)

router = APIRouter(prefix="/api/v1/account", tags=["account"])

router.post(
    "/send-verification-code",
    response_model=SendVerificationCodeResponse,
)(send_verification_code)
router.post("/login", response_model=EmailLoginResponse)(email_login)
router.post("/register-trial", response_model=TrialRegistrationResponse)(register_trial)
router.post("/leads")(capture_lead)
router.get("/me")(get_me)
router.get("/usage/summary")(get_usage_summary)
router.get("/admin/overview")(get_admin_overview)
router.get("/billing/plan")(get_plan)
router.post("/billing/byok")(update_byok)
router.post("/projects/sync")(sync_project)
router.get("/projects")(list_projects)
router.get("/team")(get_team)
router.post("/team/rename")(rename_team)
router.post("/team/members")(add_team_member)
router.post("/team/knowledge-scope")(update_team_knowledge_scope)
