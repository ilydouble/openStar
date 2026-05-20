from __future__ import annotations

from ..base import DomainSettings


class AuthSettings(DomainSettings):
    env_domains = ("auth",)

    icore_base_url: str = ""
    icore_secret: str = ""
    auth_enabled: bool = False
    jwt_secret: str = "dev-icore-jwt-secret-change-me-32-bytes"
    jwt_issuer: str = "icore-agent"
    jwt_audience: str = "icore-gateway"
    jwt_ttl_seconds: int = 86400

    # Control Plane 数据存储路径（组织、项目、验证码、线索等非用户数据）
    # 警告：默认 /tmp 路径在系统重启后会清空，生产环境务必改为持久化路径
    control_plane_store_path: str = "/tmp/icore-control-plane.json"
    import_json_users_on_startup: bool = True

    # ── 邮件服务（Resend）────────────────────────────────
    # 从 resend.com 获取 API Key，留空则仅打印到日志（开发模式）
    resend_api_key: str = ""
    # 测试阶段用 onboarding@resend.dev（无需验证域名）
    # 生产阶段换成自己的域名邮箱并在 Resend 控制台完成 DNS 验证
    resend_from_email: str = "onboarding@resend.dev"
    resend_from_name: str = "iCore"


auth_settings = AuthSettings()
