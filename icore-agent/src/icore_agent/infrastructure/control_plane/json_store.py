"""Small JSON-backed account and usage store for the first commercialization milestone."""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
import uuid
from collections.abc import Mapping
from datetime import UTC
from pathlib import Path
from typing import Any

from icore_agent.domain.user import UserProfile

from ...config import settings
from ...shared.logging.app_logger import get_logger

fallback_log = logging.getLogger(__name__)
log = get_logger(__name__)

UserPayload = UserProfile | Mapping[str, Any]


def _user_payload(user: UserPayload) -> dict[str, Any]:
    """Normalize a domain user profile or mapping into the JSON store shape."""
    if isinstance(user, UserProfile):
        return {
            "id": user.public_id,
            "name": user.name,
            "email": user.email,
            "plan": user.plan,
            "plan_label": user.plan_label,
            "organization_id": user.organization_id or "",
            "organization_name": user.organization_name or "",
            "roles": list(user.roles or ["owner"]),
            "byok": dict(user.byok or {}),
            "usage": dict(user.usage or {}),
            "created_at": int(user.created_at),
            "updated_at": int(user.updated_at),
        }
    return dict(user)


def _print_dev_verification_email(to_email: str, code: str) -> None:
    """Print the verification code to local logs for development fallback flows."""
    print(f"\n{'='*60}")
    print(f"📧 [DEV] 验证码邮件 → {to_email}")
    print(f"🔑 验证码: {code}  （10 分钟有效）")
    print(f"{'='*60}\n")


def _send_verification_email(to_email: str, code: str) -> bool:
    """Send a verification email through Resend, or print it locally when mail is not configured."""
    if not settings.resend_api_key:
        # 未配置时 fallback 到打印（本地开发用）
        _print_dev_verification_email(to_email, code)
        return True

    try:
        import resend  # type: ignore[import-not-found]
        resend.api_key = settings.resend_api_key

        html_body = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
          <h2 style="margin:0 0 8px;font-size:22px;color:#09090b">iCore 邮箱验证</h2>
          <p style="color:#52525b;margin:0 0 24px">你的验证码是：</p>
          <div style="background:#f4f4f5;border-radius:12px;padding:20px 32px;text-align:center;
                      font-size:36px;font-weight:700;letter-spacing:8px;color:#09090b">
            {code}
          </div>
          <p style="color:#71717a;font-size:13px;margin:20px 0 0">
            验证码 10 分钟内有效，请勿转发给他人。<br>
            如非本人操作，请忽略此邮件。
          </p>
        </div>
        """

        resend.Emails.send({
            "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
            "to": [to_email],
            "subject": f"{code} 是你的 iCore 验证码",
            "html": html_body,
        })
        return True
    except Exception as exc:
        log.error("resend_email_failed", error=str(exc), to=to_email)
        return False


def _emit_verification_code_event(
    email: str,
    client_ip: str,
    code: str,
    *,
    delivery_channel: str,
    delivery_result: str,
) -> None:
    """Emit a backend verification-code event to the internal logging-service."""
    metadata: dict[str, Any] = {
        "email": email,
        "client_ip": client_ip,
        "delivery_channel": delivery_channel,
        "delivery_result": delivery_result,
        "debug": settings.debug,
    }
    if settings.debug:
        metadata["verification_code"] = code

    try:
        log.info("verification_code_issued", **metadata)
    except Exception as exc:  # noqa: BLE001 - logging must not block account flows.
        fallback_log.warning("verification_code_log_emit_failed: %s", exc)


class ControlPlaneStore:
    def __init__(self) -> None:
        self._path = Path(settings.control_plane_store_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {
                "users": {},
                "tokens": {},
                "usage_events": [],
                "events": [],
                "projects": {},
                "organizations": {},
                "leads": [],
                "verification_codes": {},  # {email: {code, expires_at, ip, send_count}}
                "ip_registrations": {},  # {ip: [timestamp1, timestamp2, ...]}
            }
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            data.setdefault("users", {})
            data.setdefault("tokens", {})
            data.setdefault("usage_events", [])
            data.setdefault("events", [])
            data.setdefault("projects", {})
            data.setdefault("organizations", {})
            data.setdefault("leads", [])
            return data
        except Exception:
            return {
                "users": {},
                "tokens": {},
                "usage_events": [],
                "events": [],
                "projects": {},
                "organizations": {},
                "leads": [],
            }

    def _save(self, data: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(
            data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _should_reset_quota(self, quota_period_start: int) -> bool:
        """检查是否需要重置配额周期（每月 1 号 00:00 重置）。

        Args:
            quota_period_start: 当前周期开始时间戳

        Returns:
            True 如果当前时间已跨越到新的月份周期
        """
        if quota_period_start == 0:
            return True  # 首次使用，需要初始化

        from datetime import datetime

        period_start = datetime.fromtimestamp(
            quota_period_start, tz=UTC)
        now = datetime.now(UTC)

        # 如果当前月份大于周期开始月份，或者年份不同，需要重置
        if now.year > period_start.year:
            return True
        return now.year == period_start.year and now.month > period_start.month

    def _get_quota_period_start(self) -> int:
        """获取当前配额周期的开始时间戳（当月 1 号 00:00 UTC）。"""
        from datetime import datetime

        now = datetime.now(UTC)
        # 本月 1 号 00:00:00 UTC
        period_start = datetime(now.year, now.month, 1,
                                0, 0, 0, tzinfo=UTC)
        return int(period_start.timestamp())

    def _ensure_org_for_user(self, data: dict[str, Any], user: dict[str, Any]) -> None:
        """Ensure organization metadata exists for one normalized user payload."""
        org_id = user.get("organization_id", "")
        if org_id and org_id in data.get("organizations", {}):
            return
        now = int(time.time())
        org_id = org_id or f"org_{uuid.uuid4().hex[:12]}"
        org_name = user.get(
            "organization_name") or f"{user.get('name') or 'Team'} Team"
        user["organization_id"] = org_id
        user["organization_name"] = org_name
        data.setdefault("organizations", {})[org_id] = {
            "id": org_id,
            "name": org_name,
            "owner_user_id": user["id"],
            "knowledge_scope": "organization",
            "members": [
                {
                    "user_id": user["id"],
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "role": (user.get("roles") or ["owner"])[0],
                    "status": "active",
                    "created_at": user.get("created_at", now),
                }
            ],
            "created_at": user.get("created_at", now),
            "updated_at": now,
        }

    def send_verification_code(self, email: str, client_ip: str) -> tuple[bool, str]:
        """发送邮箱验证码（同一 IP 24 小时内最多发送 3 次）"""
        now = int(time.time())
        with self._lock:
            data = self._load()
            codes = data.setdefault("verification_codes", {})

            # 清理过期的验证码
            expired_emails = [e for e, info in codes.items(
            ) if info.get("expires_at", 0) < now]
            for e in expired_emails:
                del codes[e]

            # 检查同一 IP 24 小时内发送次数（最多 3 次）
            ip_sends = [
                info for info in codes.values()
                if info.get("ip") == client_ip and info.get("timestamp", 0) > now - 86400
            ]
            if len(ip_sends) >= 3:
                return False, "Maximum of 3 verification codes per IP within 24 hours"

            # 生成 6 位数字验证码
            code = f"{secrets.randbelow(1000000):06d}"
            codes[email.lower()] = {
                "code": code,
                "expires_at": now + 600,  # 10 分钟有效期
                "ip": client_ip,
                "timestamp": now,
            }

            self._save(data)

            sent = _send_verification_email(email, code)
            _emit_verification_code_event(
                email,
                client_ip,
                code,
                delivery_channel="resend" if settings.resend_api_key else "dev_log",
                delivery_result="sent" if sent else "failed",
            )
            if not sent:
                # 本地开发环境下，邮件服务不可用时自动降级为日志验证码，避免阻塞注册流程。
                if settings.debug:
                    log.warning(
                        "verification_email_delivery_fallback",
                        email=email,
                        client_ip=client_ip,
                    )
                    _print_dev_verification_email(email, code)
                    return True, (
                        f"Verification code sent to {email}. Valid for 10 minutes "
                        "(dev mode: check backend logs)"
                    )
                return False, "Failed to send verification code. Please try again later."

            return True, f"Verification code sent to {email}. Valid for 10 minutes."

    def verify_code(self, email: str, code: str) -> bool:
        """验证邮箱验证码"""
        now = int(time.time())
        with self._lock:
            data = self._load()
            codes = data.setdefault("verification_codes", {})
            info = codes.get(email.lower())

            if not info:
                return False

            if info.get("expires_at", 0) < now:
                del codes[email.lower()]
                self._save(data)
                return False

            if info.get("code") != code:
                return False

            # 验证成功后删除验证码（一次性使用）
            del codes[email.lower()]
            self._save(data)
            return True

    def check_ip_registration_limit(self, client_ip: str) -> bool:
        """检查 IP 注册限制（24 小时内只能注册 1 次）"""
        now = int(time.time())
        with self._lock:
            data = self._load()
            ip_regs = data.setdefault("ip_registrations", {})

            # 清理 24 小时之前的记录
            for ip in list(ip_regs.keys()):
                ip_regs[ip] = [ts for ts in ip_regs[ip] if ts > now - 86400]
                if not ip_regs[ip]:
                    del ip_regs[ip]

            # 检查是否已达到限制
            recent_count = len(ip_regs.get(client_ip, []))
            return recent_count < 1

    def issue_legacy_token(self, user_id: str) -> str:
        """Issue a legacy opaque token mapped to a user public id."""
        with self._lock:
            data = self._load()
            token = f"icore_{secrets.token_urlsafe(24)}"
            data.setdefault("tokens", {})[token] = {
                "user_id": user_id,
                "issued_at": int(time.time()),
            }
            self._save(data)
            return token

    def get_user_id_for_token(self, token: str) -> str | None:
        """Resolve a legacy opaque token to a user public id."""
        with self._lock:
            data = self._load()
            token_record = data.get("tokens", {}).get(token)
            if not token_record:
                return None
            return str(token_record.get("user_id") or "") or None

    def append_event(self, event_type: str, **payload: Any) -> None:
        """Append one control-plane audit event to the JSON store."""
        with self._lock:
            data = self._load()
            data.setdefault("events", []).append(
                {"type": event_type, "timestamp": int(time.time()), **payload}
            )
            self._save(data)

    def record_ip_registration(self, client_ip: str) -> None:
        """Record one successful registration for IP throttling."""
        now = int(time.time())
        with self._lock:
            data = self._load()
            ip_regs = data.setdefault("ip_registrations", {})
            ip_regs.setdefault(client_ip, []).append(now)
            self._save(data)

    def create_organization_for_user(self, user: UserPayload) -> None:
        """Persist organization metadata for a newly registered user."""
        payload = _user_payload(user)
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            self._save(data)

    def ensure_organization_for_user(self, user: UserPayload) -> None:
        """Ensure organization metadata exists for an existing user profile."""
        payload = _user_payload(user)
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            self._save(data)

    def get_team_profile_for_user(self, user: UserPayload) -> dict[str, Any]:
        """Return the organization profile for one user dict."""
        payload = _user_payload(user)
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            return self._team_profile_from_data(data, payload)

    def _team_profile_from_data(
        self,
        data: dict[str, Any],
        user: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a team profile response from already loaded store data."""
        org_id = user.get("organization_id", "")
        organization = data.get("organizations", {}).get(org_id) or {
            "id": org_id,
            "name": user.get("organization_name", ""),
            "knowledge_scope": "organization",
            "members": [],
        }
        return {
            "organization": {
                "id": organization["id"],
                "name": organization.get("name", ""),
                "knowledge_scope": organization.get("knowledge_scope", "organization"),
            },
            "members": organization.get("members", []),
            "current_user_id": user["id"],
        }

    def rename_organization_for_user(
        self,
        user: UserPayload,
        organization_name: str,
    ) -> dict[str, Any]:
        """Rename the organization associated with one user."""
        now = int(time.time())
        payload = _user_payload(user)
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            org_id = payload["organization_id"]
            organization = data["organizations"][org_id]
            organization["name"] = organization_name.strip()
            organization["updated_at"] = now
            self._save(data)
            updated = {**payload,
                       "organization_name": organization_name.strip()}
            return self._team_profile_from_data(data, updated)

    def add_team_member_for_user(
        self,
        user: UserPayload,
        *,
        name: str,
        email: str,
        role: str,
    ) -> dict[str, Any]:
        """Add one invited member to the user's organization."""
        now = int(time.time())
        payload = _user_payload(user)
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            org_id = payload["organization_id"]
            organization = data["organizations"][org_id]
            member = {
                "user_id": f"member_{uuid.uuid4().hex[:12]}",
                "name": name.strip(),
                "email": email.strip().lower(),
                "role": role.strip() or "viewer",
                "status": "invited",
                "created_at": now,
            }
            organization.setdefault("members", []).append(member)
            organization["updated_at"] = now
            self._save(data)
            return member

    def update_knowledge_scope_for_user(self, user: UserPayload, scope: str) -> dict[str, Any]:
        """Update the knowledge scope for the user's organization."""
        now = int(time.time())
        payload = _user_payload(user)
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            org_id = payload["organization_id"]
            organization = data["organizations"][org_id]
            organization["knowledge_scope"] = scope
            organization["updated_at"] = now
            self._save(data)
            return self._team_profile_from_data(data, payload)

    def sync_project_for_user(
        self,
        user: UserPayload,
        *,
        project_id: str,
        project_title: str,
        scenario_id: str,
        session_id: str,
        session_title: str,
        session_subtitle: str,
        attachment_count: int,
    ) -> dict[str, Any]:
        """Persist project/session metadata for one user profile."""
        now = int(time.time())
        payload = _user_payload(user)
        user_id = payload["id"]
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            projects_by_user = data.setdefault(
                "projects", {}).setdefault(user_id, {})
            project = projects_by_user.setdefault(
                project_id,
                {
                    "id": project_id,
                    "title": project_title,
                    "scenario_id": scenario_id,
                    "organization_id": payload.get("organization_id", ""),
                    "updated_at": now,
                    "sessions": {},
                },
            )
            project["title"] = project_title or project["title"]
            project["scenario_id"] = scenario_id or project.get(
                "scenario_id", "")
            project["organization_id"] = payload.get("organization_id", "")
            project["updated_at"] = now
            project["sessions"][session_id] = {
                "session_id": session_id,
                "title": session_title,
                "subtitle": session_subtitle,
                "attachment_count": max(int(attachment_count or 0), 0),
                "updated_at": now,
            }
            self._save(data)
            return self._serialize_project(project)

    def list_projects_for_user(self, user: UserPayload) -> dict[str, Any]:
        """List projects visible to the user's organization."""
        payload = _user_payload(user)
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, payload)
            org_id = payload.get("organization_id", "")
            all_projects = []
            for owner_user_id, projects_by_user in data.get("projects", {}).items():
                for project in projects_by_user.values():
                    if project.get("organization_id") == org_id:
                        serialized = self._serialize_project(project)
                        serialized["owner_user_id"] = owner_user_id
                        all_projects.append(serialized)
            all_projects.sort(
                key=lambda item: item["updated_at"], reverse=True)
            recent_sessions: list[dict[str, Any]] = []
            for project in all_projects:
                for session in project["sessions"]:
                    recent_sessions.append(
                        {
                            **session,
                            "project_id": project["id"],
                            "project_title": project["title"],
                            "scenario_id": project.get("scenario_id", ""),
                        }
                    )
            recent_sessions.sort(
                key=lambda item: item["updated_at"], reverse=True)
            return {
                "projects": all_projects[:10],
                "recent_sessions": recent_sessions[:12],
            }

    def list_legacy_json_users(self) -> list[dict[str, Any]]:
        """Return user profiles still stored in the JSON file before PostgreSQL migration."""
        with self._lock:
            data = self._load()
            users: list[dict[str, Any]] = []
            for user_id, profile in data.get("users", {}).items():
                if isinstance(profile, dict):
                    users.append(
                        {**profile, "id": profile.get("id") or user_id})
            return users

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        """Deprecated: legacy token lookup retained for adapter compatibility."""
        user_id = self.get_user_id_for_token(token)
        if not user_id:
            return None
        return {"id": user_id}

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Deprecated: user profiles are loaded from PostgreSQL."""
        _ = user_id
        return None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Deprecated: user profiles are loaded from PostgreSQL."""
        _ = email
        return None

    def issue_token_for_user(self, user_id: str) -> str:
        """Deprecated alias for legacy token issuance."""
        return self.issue_legacy_token(user_id)

    def register_trial(self, name: str, email: str, client_ip: str = "unknown") -> tuple[dict[str, Any], str]:
        """Deprecated: registration is handled by PostgreSQL repositories."""
        _ = (name, email, client_ip)
        raise RuntimeError(
            "register_trial is handled by PostgresRegistrationRepository")

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]:
        """Deprecated: BYOK settings are stored on PostgreSQL user profiles."""
        _ = (user_id, api_key, api_base, model)
        raise RuntimeError(
            "update_byok is handled by PostgresBillingSummaryRepository")

    def update_user_plan(
        self,
        user_id: str,
        new_plan: str,
        byok_enabled: bool = False,
        byok_api_key: str = "",
        byok_api_base: str = "",
        byok_model: str = "",
    ) -> dict[str, Any]:
        """Deprecated: billing plans are stored on PostgreSQL user profiles."""
        _ = (user_id, new_plan, byok_enabled,
             byok_api_key, byok_api_base, byok_model)
        raise RuntimeError(
            "update_user_plan is handled by PostgresBillingRepository")

    def get_plan_summary(self, user_id: str) -> dict[str, Any]:
        """Deprecated: plan summaries are loaded from PostgreSQL."""
        _ = user_id
        raise RuntimeError(
            "get_plan_summary is handled by PostgresBillingSummaryRepository")

    def get_team_profile(self, user_id: str) -> dict[str, Any]:
        """Deprecated: use get_team_profile_for_user with a PostgreSQL user dict."""
        _ = user_id
        raise RuntimeError(
            "get_team_profile is handled by PostgresTeamRepository")

    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]:
        """Deprecated: use rename_organization_for_user with a PostgreSQL user dict."""
        _ = (user_id, organization_name)
        raise RuntimeError(
            "rename_organization is handled by PostgresTeamRepository")

    def add_team_member(self, user_id: str, *, name: str, email: str, role: str) -> dict[str, Any]:
        """Deprecated: use add_team_member_for_user with a PostgreSQL user dict."""
        _ = (user_id, name, email, role)
        raise RuntimeError(
            "add_team_member is handled by PostgresTeamRepository")

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        """Deprecated: use update_knowledge_scope_for_user with a PostgreSQL user dict."""
        _ = (user_id, scope)
        raise RuntimeError(
            "update_knowledge_scope is handled by PostgresTeamRepository")

    def check_quota(self, user_id: str, kind: str, amount: int = 1) -> tuple[bool, str | None]:
        """Deprecated: quota checks are handled by PostgreSQL user profiles."""
        _ = (user_id, kind, amount)
        raise RuntimeError("check_quota is handled by UsageService")

    def consume_quota(self, user_id: str, kind: str, amount: int = 1) -> None:
        """Deprecated: quota consumption is handled by PostgreSQL user profiles."""
        _ = (user_id, kind, amount)
        raise RuntimeError(
            "consume_quota is handled by UsageService")

    def record_usage_event(
        self,
        *,
        user_id: str,
        session_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        estimated_cost: float,
    ) -> None:
        with self._lock:
            data = self._load()
            data["usage_events"].append(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "session_id": session_id,
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost": estimated_cost,
                    "timestamp": int(time.time()),
                }
            )
            self._save(data)

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            events = [evt for evt in data["usage_events"]
                      if evt["user_id"] == user_id]
            total_cost = round(sum(evt["estimated_cost"] for evt in events), 6)
            total_tokens = sum(evt["total_tokens"] for evt in events)
            by_model: dict[str, dict[str, Any]] = {}
            for evt in events:
                entry = by_model.setdefault(
                    evt["model"], {"tokens": 0, "cost": 0.0, "calls": 0})
                entry["tokens"] += evt["total_tokens"]
                entry["cost"] += evt["estimated_cost"]
                entry["calls"] += 1
            for entry in by_model.values():
                entry["cost"] = round(entry["cost"], 6)
            return {"total_tokens": total_tokens, "total_cost": total_cost, "by_model": by_model, "events": events[-20:]}

    def admin_overview(self, users: list[UserPayload]) -> dict[str, Any]:
        """Return admin usage and account metrics for a user set."""
        user_payloads = [_user_payload(user) for user in users]
        with self._lock:
            data = self._load()
            usage_events = data["usage_events"]
            leads = data.get("leads", [])
            now = int(time.time())
            active_window = now - 7 * 24 * 3600
            recent_trials = sum(1 for evt in data["events"] if evt.get(
                "type") == "trial_registered" and evt.get("timestamp", 0) >= active_window)
            by_model: dict[str, dict[str, Any]] = {}
            total_cost = 0.0
            total_tokens = 0
            for evt in usage_events:
                total_cost += float(evt.get("estimated_cost", 0.0) or 0.0)
                total_tokens += int(evt.get("total_tokens", 0) or 0)
                entry = by_model.setdefault(
                    evt["model"], {"calls": 0, "tokens": 0, "cost": 0.0})
                entry["calls"] += 1
                entry["tokens"] += int(evt.get("total_tokens", 0) or 0)
                entry["cost"] += float(evt.get("estimated_cost", 0.0) or 0.0)
            for entry in by_model.values():
                entry["cost"] = round(entry["cost"], 6)
            heavy_users = sorted(
                (
                    {
                        "user_id": user["id"],
                        "email": user["email"],
                        "tokens": int((user.get("usage") or {}).get("token_count", 0)),
                        "messages": int((user.get("usage") or {}).get("message_count", 0)),
                        "plan": user.get("plan", "trial"),
                    }
                    for user in user_payloads
                ),
                key=lambda item: (item["tokens"], item["messages"]),
                reverse=True,
            )[:5]
            return {
                "users": {
                    "total": len(user_payloads),
                    "active_7d": sum(
                        1
                        for user in user_payloads
                        if int(user.get("updated_at", 0) or 0) >= active_window
                    ),
                    "trial": sum(
                        1
                        for user in user_payloads
                        if user.get("plan") in ("trial", "free")
                    ),
                    "byok_enabled": sum(
                        1
                        for user in user_payloads
                        if (user.get("byok") or {}).get("enabled")
                    ),
                    "new_trials_7d": recent_trials,
                },
                "leads": {
                    "total": len(leads),
                    "enterprise": sum(1 for lead in leads if lead.get("intent") == "enterprise"),
                    "demo": sum(1 for lead in leads if lead.get("intent") == "demo"),
                },
                "usage": {
                    "total_calls": len(usage_events),
                    "total_tokens": total_tokens,
                    "total_cost": round(total_cost, 6),
                    "by_model": by_model,
                },
                "heavy_users": heavy_users,
            }

    def create_lead(
        self,
        *,
        name: str,
        email: str,
        company: str,
        team_size: str,
        use_case: str,
        needs_byok: bool,
        needs_private_deploy: bool,
        source: str,
        intent: str,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            data = self._load()
            lead = {
                "id": f"lead_{uuid.uuid4().hex[:12]}",
                "name": name.strip(),
                "email": email.strip().lower(),
                "company": company.strip(),
                "team_size": team_size.strip(),
                "use_case": use_case.strip(),
                "needs_byok": bool(needs_byok),
                "needs_private_deploy": bool(needs_private_deploy),
                "source": source.strip(),
                "intent": intent.strip() or "demo",
                "created_at": now,
            }
            data.setdefault("leads", []).append(lead)
            data["events"].append(
                {"type": "lead_created", "email": lead["email"], "intent": lead["intent"], "timestamp": now})
            self._save(data)
            return lead

    @staticmethod
    def _serialize_project(project: dict[str, Any]) -> dict[str, Any]:
        sessions = sorted(
            project.get("sessions", {}).values(),
            key=lambda item: item.get("updated_at", 0),
            reverse=True,
        )
        return {
            "id": project["id"],
            "title": project["title"],
            "scenario_id": project.get("scenario_id", ""),
            "updated_at": project.get("updated_at", 0),
            "sessions_count": len(sessions),
            "assets_count": sum(int(item.get("attachment_count", 0) or 0) for item in sessions),
            "sessions": sessions[:6],
        }


control_plane_store = ControlPlaneStore()
