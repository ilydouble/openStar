"""Small JSON-backed account and usage store for the first commercialization milestone."""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from ..config import settings

log = logging.getLogger(__name__)


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
        import resend
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

_DEFAULT_USAGE = {
    "message_count": 0,
    "token_count": 0,
    "image_count": 0,
    "attachment_count": 0,
    "quota_period_start": 0,  # Unix timestamp of current quota period start
}

_PLAN_LIMITS = {
    "trial": {
        "message_limit": 0,
        "token_limit": 0,
        "image_limit": 0,
        "attachment_limit": 0,
        "label": "Trial",
    },
    "free": {
        "message_limit": 80,
        "token_limit": 240_000,
        "image_limit": 20,
        "attachment_limit": 40,
        "label": "Free",
    },
    "team": {
        "message_limit": 800,
        "token_limit": 2_000_000,
        "image_limit": 200,
        "attachment_limit": 400,
        "label": "Team",
    },
    "enterprise": {
        "message_limit": 10_000,
        "token_limit": 20_000_000,
        "image_limit": 2_000,
        "attachment_limit": 10_000,
        "label": "Enterprise",
    },
    "byok": {
        "message_limit": 800,
        "token_limit": 0,
        "image_limit": 200,
        "attachment_limit": 400,
        "label": "BYOK",
    },
}


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
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _should_reset_quota(self, quota_period_start: int) -> bool:
        """检查是否需要重置配额周期（每月 1 号 00:00 重置）。

        Args:
            quota_period_start: 当前周期开始时间戳

        Returns:
            True 如果当前时间已跨越到新的月份周期
        """
        if quota_period_start == 0:
            return True  # 首次使用，需要初始化

        from datetime import datetime, timezone

        period_start = datetime.fromtimestamp(quota_period_start, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # 如果当前月份大于周期开始月份，或者年份不同，需要重置
        if now.year > period_start.year:
            return True
        if now.year == period_start.year and now.month > period_start.month:
            return True

        return False

    def _get_quota_period_start(self) -> int:
        """获取当前配额周期的开始时间戳（当月 1 号 00:00 UTC）。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        # 本月 1 号 00:00:00 UTC
        period_start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        return int(period_start.timestamp())

    def _ensure_org_for_user(self, data: dict[str, Any], user: dict[str, Any]) -> None:
        org_id = user.get("organization_id", "")
        if org_id and org_id in data.get("organizations", {}):
            return
        now = int(time.time())
        org_id = org_id or f"org_{uuid.uuid4().hex[:12]}"
        org_name = user.get("organization_name") or f"{user.get('name') or 'Team'} Team"
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
            expired_emails = [e for e, info in codes.items() if info.get("expires_at", 0) < now]
            for e in expired_emails:
                del codes[e]

            # 检查同一 IP 24 小时内发送次数（最多 3 次）
            ip_sends = [
                info for info in codes.values()
                if info.get("ip") == client_ip and info.get("timestamp", 0) > now - 86400
            ]
            if len(ip_sends) >= 3:
                return False, "同一 IP 24 小时内最多发送 3 次验证码"

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
            if not sent:
                # 本地开发环境下，邮件服务不可用时自动降级为日志验证码，避免阻塞注册流程。
                if settings.debug:
                    log.warning("verification_email_delivery_fallback email=%s client_ip=%s", email, client_ip)
                    _print_dev_verification_email(email, code)
                    return True, f"验证码已发送到 {email}，10 分钟内有效（开发模式：请查看后端日志）"
                return False, "验证码发送失败，请稍后重试"

            return True, f"验证码已发送到 {email}，10 分钟内有效"

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

    def register_trial(self, name: str, email: str, client_ip: str = "unknown") -> tuple[dict[str, Any], str]:
        now = int(time.time())
        with self._lock:
            data = self._load()
            for user in data["users"].values():
                if user["email"].lower() == email.lower():
                    self._ensure_org_for_user(data, user)
                    user["updated_at"] = now
                    token = self._issue_token(data, user["id"])
                    self._save(data)
                    return user, token

            user_id = str(uuid.uuid4())
            org_id = f"org_{uuid.uuid4().hex[:12]}"
            user = {
                "id": user_id,
                "name": name.strip(),
                "email": email.strip().lower(),
                "plan": "trial",
                "plan_label": _PLAN_LIMITS["trial"]["label"],
                "organization_id": org_id,
                "organization_name": f"{name.strip() or 'Trial'} Team",
                "roles": ["owner"],
                "byok": {"enabled": False, "api_key": "", "api_base": "", "model": ""},
                "usage": dict(_DEFAULT_USAGE),
                "created_at": now,
                "updated_at": now,
            }
            data["users"][user_id] = user
            data.setdefault("organizations", {})[org_id] = {
                "id": org_id,
                "name": user["organization_name"],
                "owner_user_id": user_id,
                "knowledge_scope": "organization",
                "members": [
                    {
                        "user_id": user_id,
                        "name": user["name"],
                        "email": user["email"],
                        "role": "owner",
                        "status": "active",
                        "created_at": now,
                    }
                ],
                "created_at": now,
                "updated_at": now,
            }
            token = self._issue_token(data, user_id)
            data["events"].append({"type": "trial_registered", "user_id": user_id, "timestamp": now})

            # 记录 IP 注册
            ip_regs = data.setdefault("ip_registrations", {})
            ip_regs.setdefault(client_ip, []).append(now)

            self._save(data)
            return user, token

    def _issue_token(self, data: dict[str, Any], user_id: str) -> str:
        token = f"icore_{secrets.token_urlsafe(24)}"
        data["tokens"][token] = {"user_id": user_id, "issued_at": int(time.time())}
        return token

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._load()
            token_record = data["tokens"].get(token)
            if not token_record:
                return None
            user = data["users"].get(token_record["user_id"])
            if user:
                self._ensure_org_for_user(data, user)
                self._save(data)
            return user

    def update_byok(self, user_id: str, api_key: str, api_base: str, model: str) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            user["byok"] = {
                "enabled": bool(api_key),
                "api_key": api_key.strip(),
                "api_base": api_base.strip(),
                "model": model.strip(),
            }
            user["updated_at"] = now
            data["events"].append({"type": "byok_updated", "user_id": user_id, "timestamp": now})
            self._save(data)
            return user["byok"]

    def update_user_plan(
        self,
        user_id: str,
        new_plan: str,
        byok_enabled: bool = False,
        byok_api_key: str = "",
        byok_api_base: str = "",
        byok_model: str = "",
    ) -> dict[str, Any]:
        """更新用户套餐（手动升级或降级）"""
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            now = int(time.time())

            old_plan = user["plan"]
            user["plan"] = new_plan
            user["plan_label"] = _PLAN_LIMITS[new_plan]["label"]

            # 如果切换到 BYOK，更新配置
            if byok_enabled:
                user["byok"] = {
                    "enabled": True,
                    "api_key": byok_api_key.strip(),
                    "api_base": byok_api_base.strip(),
                    "model": byok_model.strip(),
                }

            user["updated_at"] = now
            data["events"].append({
                "type": "plan_updated",
                "user_id": user_id,
                "old_plan": old_plan,
                "new_plan": new_plan,
                "timestamp": now,
            })
            self._save(data)
            return user

    def get_plan_summary(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            limits = _PLAN_LIMITS[user["plan"]]
            usage = user.get("usage") or dict(_DEFAULT_USAGE)

            # 计算下次重置时间（下月 1 号 00:00 UTC）
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            if now.month == 12:
                next_reset = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            else:
                next_reset = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

            return {
                "plan": user["plan"],
                "label": limits["label"],
                "limits": {
                    "messages": limits["message_limit"],
                    "tokens": limits["token_limit"],
                    "images": limits["image_limit"],
                    "attachments": limits["attachment_limit"],
                },
                "usage": {
                    "messages": usage["message_count"],
                    "tokens": usage["token_count"],
                    "images": usage["image_count"],
                    "attachments": usage["attachment_count"],
                },
                "quota_period": {
                    "start": usage.get("quota_period_start", 0),
                    "next_reset": int(next_reset.timestamp()),
                },
                "byok": user.get("byok") or {"enabled": False, "api_key": "", "api_base": "", "model": ""},
            }

    def get_team_profile(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
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
                "current_user_id": user_id,
            }

    def rename_organization(self, user_id: str, organization_name: str) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            org_id = user["organization_id"]
            organization = data["organizations"][org_id]
            organization["name"] = organization_name.strip()
            organization["updated_at"] = now
            for member in organization.get("members", []):
                if member.get("user_id") == user_id:
                    break
            user["organization_name"] = organization["name"]
            user["updated_at"] = now
            self._save(data)
            return {
                "organization": {
                    "id": organization["id"],
                    "name": organization["name"],
                    "knowledge_scope": organization.get("knowledge_scope", "organization"),
                },
                "members": organization.get("members", []),
                "current_user_id": user_id,
            }

    def add_team_member(self, user_id: str, *, name: str, email: str, role: str) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            org_id = user["organization_id"]
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

    def update_knowledge_scope(self, user_id: str, scope: str) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            org_id = user["organization_id"]
            organization = data["organizations"][org_id]
            organization["knowledge_scope"] = scope
            organization["updated_at"] = now
            self._save(data)
            return {
                "organization": {
                    "id": organization["id"],
                    "name": organization.get("name", ""),
                    "knowledge_scope": organization.get("knowledge_scope", "organization"),
                },
                "members": organization.get("members", []),
                "current_user_id": user_id,
            }

    def check_quota(self, user_id: str, kind: str, amount: int = 1) -> tuple[bool, str | None]:
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            plan = user["plan"]
            usage = user.setdefault("usage", dict(_DEFAULT_USAGE))

            # 检查是否需要重置配额周期
            quota_period_start = usage.get("quota_period_start", 0)
            if self._should_reset_quota(quota_period_start):
                # 重置所有计数器，但保留 quota_period_start 字段
                usage["message_count"] = 0
                usage["token_count"] = 0
                usage["image_count"] = 0
                usage["attachment_count"] = 0
                usage["quota_period_start"] = self._get_quota_period_start()
                user["updated_at"] = int(time.time())
                self._save(data)

            limits = _PLAN_LIMITS[plan]
            if kind == "messages":
                limit = limits["message_limit"]
                used = usage["message_count"]
            elif kind == "tokens":
                limit = limits["token_limit"]
                used = usage["token_count"]
            elif kind == "images":
                limit = limits["image_limit"]
                used = usage["image_count"]
            else:
                limit = limits["attachment_limit"]
                used = usage["attachment_count"]

            if limit and used + amount > limit:
                return False, f"{kind} quota exceeded for {plan}"
            return True, None

    def consume_quota(self, user_id: str, kind: str, amount: int = 1) -> None:
        with self._lock:
            data = self._load()
            user = data["users"][user_id]
            self._ensure_org_for_user(data, user)
            usage = user.setdefault("usage", dict(_DEFAULT_USAGE))

            # 检查是否需要重置配额周期（consume 时也需要检查）
            quota_period_start = usage.get("quota_period_start", 0)
            if self._should_reset_quota(quota_period_start):
                usage["message_count"] = 0
                usage["token_count"] = 0
                usage["image_count"] = 0
                usage["attachment_count"] = 0
                usage["quota_period_start"] = self._get_quota_period_start()

            if kind == "messages":
                usage["message_count"] += amount
            elif kind == "tokens":
                usage["token_count"] += amount
            elif kind == "images":
                usage["image_count"] += amount
            else:
                usage["attachment_count"] += amount
            user["updated_at"] = int(time.time())
            self._save(data)

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
            user = data["users"].get(user_id)
            if user:
                usage = user.setdefault("usage", dict(_DEFAULT_USAGE))
                usage["token_count"] += total_tokens
                user["updated_at"] = int(time.time())
            self._save(data)

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            events = [evt for evt in data["usage_events"] if evt["user_id"] == user_id]
            total_cost = round(sum(evt["estimated_cost"] for evt in events), 6)
            total_tokens = sum(evt["total_tokens"] for evt in events)
            by_model: dict[str, dict[str, Any]] = {}
            for evt in events:
                entry = by_model.setdefault(evt["model"], {"tokens": 0, "cost": 0.0, "calls": 0})
                entry["tokens"] += evt["total_tokens"]
                entry["cost"] += evt["estimated_cost"]
                entry["calls"] += 1
            for entry in by_model.values():
                entry["cost"] = round(entry["cost"], 6)
            return {"total_tokens": total_tokens, "total_cost": total_cost, "by_model": by_model, "events": events[-20:]}

    def admin_overview(self) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            users = list(data["users"].values())
            usage_events = data["usage_events"]
            leads = data.get("leads", [])
            now = int(time.time())
            active_window = now - 7 * 24 * 3600
            recent_trials = sum(1 for evt in data["events"] if evt.get("type") == "trial_registered" and evt.get("timestamp", 0) >= active_window)
            by_model: dict[str, dict[str, Any]] = {}
            total_cost = 0.0
            total_tokens = 0
            for evt in usage_events:
                total_cost += float(evt.get("estimated_cost", 0.0) or 0.0)
                total_tokens += int(evt.get("total_tokens", 0) or 0)
                entry = by_model.setdefault(evt["model"], {"calls": 0, "tokens": 0, "cost": 0.0})
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
                    for user in users
                ),
                key=lambda item: (item["tokens"], item["messages"]),
                reverse=True,
            )[:5]
            return {
                "users": {
                    "total": len(users),
                    "active_7d": sum(1 for user in users if int(user.get("updated_at", 0) or 0) >= active_window),
                    "trial": sum(1 for user in users if user.get("plan") == "trial"),
                    "byok_enabled": sum(1 for user in users if (user.get("byok") or {}).get("enabled")),
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
            data["events"].append({"type": "lead_created", "email": lead["email"], "intent": lead["intent"], "timestamp": now})
            self._save(data)
            return lead

    def sync_project_session(
        self,
        *,
        user_id: str,
        project_id: str,
        project_title: str,
        scenario_id: str,
        session_id: str,
        session_title: str,
        session_subtitle: str,
        attachment_count: int,
    ) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, data["users"][user_id])
            projects_by_user = data.setdefault("projects", {}).setdefault(user_id, {})
            project = projects_by_user.setdefault(
                project_id,
                {
                    "id": project_id,
                    "title": project_title,
                    "scenario_id": scenario_id,
                    "organization_id": data["users"][user_id].get("organization_id", ""),
                    "updated_at": now,
                    "sessions": {},
                },
            )
            project["title"] = project_title or project["title"]
            project["scenario_id"] = scenario_id or project.get("scenario_id", "")
            project["organization_id"] = data["users"][user_id].get("organization_id", "")
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

    def list_projects(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            self._ensure_org_for_user(data, data["users"][user_id])
            org_id = data["users"][user_id].get("organization_id", "")
            all_projects = []
            for owner_user_id, projects_by_user in data.get("projects", {}).items():
                for project in projects_by_user.values():
                    if project.get("organization_id") == org_id:
                        serialized = self._serialize_project(project)
                        serialized["owner_user_id"] = owner_user_id
                        all_projects.append(serialized)
            projects = all_projects
            projects.sort(key=lambda item: item["updated_at"], reverse=True)
            recent_sessions: list[dict[str, Any]] = []
            for project in projects:
                for session in project["sessions"]:
                    recent_sessions.append(
                        {
                            **session,
                            "project_id": project["id"],
                            "project_title": project["title"],
                            "scenario_id": project.get("scenario_id", ""),
                        }
                    )
            recent_sessions.sort(key=lambda item: item["updated_at"], reverse=True)
            return {
                "projects": projects[:10],
                "recent_sessions": recent_sessions[:12],
            }

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
