"""Application settings via pydantic-settings (reads from .env)."""

import structlog
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

log = structlog.get_logger()


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

    # 关闭 Z.AI GLM 系列的思考模式（thinking=disabled）。
    # 关闭后：
    #   • 请求体不再回传 reasoning_content，消除
    #     "reasoningContent is not supported in multi-turn" 警告
    #   • 上下文占用与首 token 延迟均下降
    #   • 代价：复杂推理类任务质量略降；本项目 orchestrator 为纯路由、
    #     子 agent 多为工具编排，对链式思考依赖不高，默认关闭。
    disable_thinking: bool = True

    # LiteLLM num_retries：指数退避重试同一模型的同一请求。
    # 在我们这种"持续 RPM 超限"的失败模式下，重试只会拉长总耗时而几乎不
    # 改变成功率，所以默认关掉；真兜底靠下面的 fallbacks 模型降级。
    llm_num_retries: int = Field(0, ge=0, le=10)

    def litellm_kwargs(self) -> dict:
        """返回所有需要透传给 LiteLLMModel 的额外参数。"""
        kwargs: dict = {}
        if self.model_api_base:
            kwargs["api_base"] = self.model_api_base
        if self.model_api_key:
            kwargs["api_key"] = self.model_api_key
        if self.disable_thinking:
            # Z.AI Chat Completions 扩展字段（GLM-4.5+ / GLM-4.6V / GLM-4.7）。
            # 必须走 extra_body 注入请求 JSON —— 作为顶层 kwarg 会被 LiteLLM
            # 原样转发到 AsyncCompletions.create() 触发
            # "unexpected keyword argument 'thinking'" 报错。
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        # 429 / 500 / 503 时自动切换到 fast 模型重跑当次请求。Z.AI 按模型
        # 独立计 RPM，flagship 撞限流时 fast 通常还有余量 —— 比无脑重试更
        # 能把请求救回来，且延迟更短（fast 首 token 快）。
        if self.model_id_fast and self.model_id_fast != self.model_id:
            kwargs["fallbacks"] = [self.model_id_fast]
        if self.llm_num_retries > 0:
            kwargs["num_retries"] = self.llm_num_retries
        log.info("litellm_kwargs_resolved", kwargs=kwargs)
        return kwargs

    # ── Strands Orchestrator ─────────────────────────────
    agent_max_tokens: int = 8192
    agent_temperature: float = Field(0.1, ge=0.0, le=1.0)

    # ── Conversation Memory (Redis) ─────────────────────
    redis_url: str = "redis://localhost:6379/0"
    memory_ttl_seconds: int = 86400  # 24 h
    # 滚动摘要：消息超过 max 条时，压缩旧消息，只保留最近 keep_recent 条原文
    memory_max_messages: int = 20    # 触发压缩的阈值
    memory_keep_recent: int = 8      # 压缩后保留的最近消息数

    # ── Auth (validates tokens via iCore ft-base) ─────────
    icore_base_url: str = ""
    icore_secret: str = ""
    auth_enabled: bool = False          # set True in production

    # ── API Keys（由 load_dotenv 写入 os.environ，LiteLLM 自动读取）──
    zai_api_key: str = ""       # zai/glm-* 模型使用，对应 ZAI_API_KEY
    anthropic_api_key: str = "" # anthropic/* 模型使用
    openai_api_key: str = ""    # openai/* 模型使用

    # ── Zhipu Embedding（供 ChromaDB RAG 使用）─────────────
    zhipu_api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_embed_model: str = "embedding-3"

    # ── ChromaDB (文档 RAG) ───────────────────────────────
    chroma_path: str = "/tmp/icore-chroma"   # 持久化目录；生产换绝对路径
    chroma_collection: str = "icore_docs"    # 基础 collection 名
    rag_chunk_size: int = 500                # 每个分块的最大字符数
    rag_chunk_overlap: int = 50             # 相邻分块的重叠字符数
    rag_top_k: int = 5                      # 默认检索返回条数

    # ── Tools ─────────────────────────────────────────────
    tavily_api_key: str = ""
    file_ops_max_size_mb: int = 10

    # ── Multi-modal 模型（视觉理解 / 图像生成）────────────
    # 视觉理解：zai/glm-4.6v-flash 免费，走 LiteLLM OpenAI-compatible vision
    vision_model_id: str = "zai/glm-4.6v-flash"
    # 图像生成：cogview-4，不走 LiteLLM，走 /images/generations REST
    image_gen_model_id: str = "cogview-4"
    image_gen_base: str = "https://api.z.ai/api/paas/v4"
    # 生成图片本地保存路径（session 子目录）——供前端 <img> 引用
    image_save_dir: str = "/tmp/icore-images"
    # 图片附件上限（Zhipu 文档：单图 5MB，6000x6000 像素）
    image_upload_max_mb: int = 5

    # ── 结构化数据上传（Data agent）────────────────────────
    # 支持 .csv / .xlsx / .xls；保存到 sequential_workspace 下的 data/{session}/ 子目录
    # 20 MB CSV ≈ 数十万行，足够 BI 级分析；超过则走分块 / 取样
    data_upload_max_mb: int = 20
    # schema + head(N) 注入 prompt 的预览行数
    data_preview_rows: int = 10

    # 智谱联网搜索引擎档位（使用 ZAI_API_KEY，无需额外 key）
    # 可选值: search_std | search_pro | search_pro_sogou | search_pro_quark
    # search_std:        基础版，0.01¥/次，日常查询
    # search_pro:        高级版，0.03¥/次，多引擎，召回率更高
    # search_pro_sogou:  搜狗，0.05¥/次，覆盖腾讯生态 + 知乎
    # search_pro_quark:  夸克，0.05¥/次，精准垂直内容
    zhipu_search_engine: str = "search_std"


# Singleton — import this everywhere
settings = Settings()
