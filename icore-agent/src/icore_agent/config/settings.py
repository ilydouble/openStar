"""Application settings via pydantic-settings (reads from .env)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────
    app_name: str = "iCore Agent Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # ── LiteLLM 模型配置 ──────────────────────────────────
    # 标准 LiteLLM 格式: "provider/model-name"，例如:
    #   anthropic/claude-sonnet-4-5   → 直连 Anthropic
    #   openai/gpt-4o                 → 直连 OpenAI
    #   openai/glm-4.7                → OpenAI 兼容接口（配合 MODEL_API_BASE）
    #   gemini/gemini-2.0-flash       → 直连 Google Gemini
    model_id: str = "zai/glm-4.7"
    model_id_fast: str = "zai/glm-4.7"

    # OpenAI 兼容接口的自定义 base URL 和 API Key
    # 留空则 LiteLLM 使用各 provider 的默认端点
    model_api_base: str = ""   # e.g. https://api.z.ai/api/paas/v4
    model_api_key: str = ""    # e.g. Z.AI / 私有部署的 key

    # ── Sequential Agent (mini-SWE-agent style) ───────────
    sequential_model: str = ""  # 空 = 自动使用 model_id
    sequential_max_steps: int = Field(30, ge=1, le=100)
    sequential_timeout_per_step: int = Field(60, ge=5, le=600)
    sequential_workspace: str = "/tmp/icore-seq-workspace"

    @property
    def effective_sequential_model(self) -> str:
        return self.sequential_model or self.model_id

    def litellm_kwargs(self) -> dict:
        """返回所有需要透传给 LiteLLMModel 的额外参数。"""
        kwargs: dict = {}
        if self.model_api_base:
            kwargs["api_base"] = self.model_api_base
        if self.model_api_key:
            kwargs["api_key"] = self.model_api_key
        return kwargs

    # ── Strands Orchestrator ─────────────────────────────
    agent_max_tokens: int = 8192
    agent_temperature: float = Field(0.1, ge=0.0, le=1.0)

    # ── Conversation Memory (Redis) ─────────────────────
    redis_url: str = "redis://localhost:6379/0"
    memory_ttl_seconds: int = 86400  # 24 h

    # ── Auth (validates tokens via iCore ft-base) ─────────
    icore_base_url: str = ""
    icore_secret: str = ""
    auth_enabled: bool = False          # set True in production

    # ── API Keys（由 load_dotenv 写入 os.environ，LiteLLM 自动读取）──
    zai_api_key: str = ""       # zai/glm-* 模型使用，对应 ZAI_API_KEY
    anthropic_api_key: str = "" # anthropic/* 模型使用
    openai_api_key: str = ""    # openai/* 模型使用

    # ── Tools ─────────────────────────────────────────────
    tavily_api_key: str = ""
    file_ops_max_size_mb: int = 10


# Singleton — import this everywhere
settings = Settings()
