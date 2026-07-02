"""Account API handler exports."""

from .auth import email_login, register_trial, send_verification_code
from .billing import get_plan, simulate_payment_success, update_byok
from .lead import capture_lead
from .memory import delete_memory_fact, get_memory, update_memory_fact
from .profile import get_admin_overview, get_me, get_usage_summary
from .project import list_projects, sync_project
from .team import add_team_member, get_team, rename_team, update_team_knowledge_scope

__all__ = [
    "add_team_member",
    "capture_lead",
    "delete_memory_fact",
    "email_login",
    "get_admin_overview",
    "get_me",
    "get_memory",
    "get_plan",
    "get_team",
    "get_usage_summary",
    "list_projects",
    "register_trial",
    "rename_team",
    "send_verification_code",
    "simulate_payment_success",
    "sync_project",
    "update_byok",
    "update_memory_fact",
    "update_team_knowledge_scope",
]
