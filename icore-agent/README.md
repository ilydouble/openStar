# iCore Agent Backend

基于 FastAPI 和 Strands Agents 的后端服务，提供企业级 AI 代理能力。

## 功能特性

- 🤖 多 Agent 协调（研究、代码、知识库）
- 🛠️ 丰富的工具集成（搜索、API 调用、代码执行、文件操作）
- 🔄 流式响应（SSE）
- 🌐 多模型支持（通过 LiteLLM）
- 💾 对话记忆（Redis）
- 🔒 可配置的认证
- 🤖 Pi Agent — 独立代码分析微服务，具备只读文件工具（ls、read、grep、find），通过 pi-source-service Node.js 服务提供能力
- 📁 Pi 项目上传与持久化 — 用户可上传完整项目文件夹（≤2GB / 10万文件），归档校验后存入 MinIO（`pi_workspaces` 表 + `icore-pi-workspaces` bucket），跨会话/重启可持久恢复
- 🔒 Pi 强沙箱隔离 — 按 `{用户ID}/{工作区ID}` 解压隔离目录；pi-source-service 二次校验所有文件操作的路径包含性（containment guard），拒绝越权访问宿主机或他人项目

## 快速开始

```bash
# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
for file in dotenv/.env.*.example; do cp "$file" "${file%.example}"; done
# 编辑 dotenv/.env.llm 配置你的 API Key

# 启动服务
# 方式1：本地直接运行（推荐开发时使用）
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python -m uvicorn icore_agent.main:app --reload --host 0.0.0.0 --port 8080

# 方式2：使用命令行工具（需要先 pip install -e .）
icore-agent
```

## 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| MODEL_ID | 主力模型 ID | zai/glm-4.7 |
| ZAI_API_KEY | 智谱 API Key | - |
| ZAI_BASE_URL | 智谱 API 地址 | https://open.bigmodel.cn/api/paas/v4/ |
| ANTHROPIC_API_KEY | Anthropic API Key | - |
| OPENAI_API_KEY | OpenAI API Key | - |
| REDIS_URL | Redis 连接地址 | redis://redis:6379/0 |
| DB_HOST | PostgreSQL 主机 | postgres |
| DB_INTERNAL_PORT | PostgreSQL 容器内部端口，也是后端连接端口 | 5432 |
| DB_HOST_PORT | PostgreSQL 映射到宿主机的端口 | 5432 |
| DB_USER | PostgreSQL 用户 | icore_agent |
| DB_PASSWORD | PostgreSQL 密码 | change-me |
| DB_NAME | PostgreSQL 数据库 | icore_agent_db |
| AGENT_MAX_TOKENS | 最大 token 数 | 8192 |
| AGENT_TEMPERATURE | 温度参数 | 0.1 |
| TIMEOUT_INTERVAL | LLM 请求超时秒数 | 30 |
| MAX_RETRIES | LLM 请求最大重试次数 | 3 |
| PI_SERVICE_URL | Pi Agent 微服务地址 | http://pi-service:11002 |
| PI_SERVICE_PORT | Pi Agent 服务端口 | 11002 |
| PI_PROVIDER | Pi Agent 使用的 LLM 提供商 | zai |
| PI_MODEL_ID | Pi Agent 使用的模型 ID | glm-4.7 |
| PI_MAX_TOKENS | Pi Agent 最大 token 数 | 8192 |
| PI_BASE_URL | Pi Agent API 地址覆盖（仅 zai/zai-coding-cn） | https://open.bigmodel.cn/api/paas/v4 |
| PI_WORKSPACE_ROOT | pi-source-service 侧的项目沙箱根目录（须与下方 `pi_workspace_sandbox_root` 指向同一共享卷路径，否则沙箱二次校验会全部失败） | /workspace/projects |
| PI_WORKSPACE_BUCKET (`pi_workspace_bucket`) | 上传项目归档的持久化 MinIO bucket | icore-pi-workspaces |
| PI_WORKSPACE_MAX_SIZE_MB (`pi_workspace_max_size_mb`) | 单个项目归档允许的最大体积（MB） | 2048 |
| PI_WORKSPACE_MAX_FILES (`pi_workspace_max_files`) | 单个项目归档允许的最大文件数 | 100000 |
| PI_WORKSPACE_UPLOAD_URL_EXPIRES_IN (`pi_workspace_upload_url_expires_in`) | 预签名上传地址的有效期（秒） | 1800 |
| PI_WORKSPACE_SANDBOX_ROOT (`pi_workspace_sandbox_root`) | icore-agent 侧解压沙箱的本地根目录（必须挂载到与 pi-service 相同的共享卷） | /workspace/projects |

> `PI_WORKSPACE_*` 中标注了 Python 字段名（括号内）的几项实际读取自 `dotenv/.env.storage`
> （`StorageSettings`，因为它们与 MinIO/对象存储是同一域），其余 `PI_*` 来自 `dotenv/.env.pi`。

环境变量按业务域拆分到 `dotenv/.env.{domain}`，模板文件为
`dotenv/.env.{domain}.example`。真实 `.env.{domain}` 文件只用于本地运行，不提交。

## Docker Compose

```bash
./compose.sh up -d --build
./compose.sh logs -f icore-agent
```

`compose.sh` 会自动为 Docker Compose 加载所有分域环境变量文件。

Pi Agent 微服务（`pi-source-service`）作为独立容器运行，通过 `infrastructure/docker/compose/pi-source-service.yml` 纳入编排。

**Pi 项目沙箱共享卷**：`icore-agent` 与 `pi-source-service` 共享一个具名卷
`pi-projects-workspace`（定义于 `base.yml`，分别挂载到两侧的 `/workspace/projects`，
路径必须一致 —— 见上方 `PI_WORKSPACE_ROOT` / `pi_workspace_sandbox_root` 说明）：
icore-agent 把用户上传并校验通过的项目归档解压到这里，pi-source-service 的只读
工具据此分析项目源码。

由于该卷首次创建时默认 `root:root` 属主，而 `icore-agent` 以非特权用户
`icore`（uid/gid 999）运行，`backend.yml` 中额外声明了一次性初始化容器
`pi-workspace-volume-init`（`busybox`镜像，模式参考 `minio-init`），每次
`up` 时自动将该卷 chown 为 `999:999` —— 全新部署或 `down -v` 后重建卷都无需
任何手动干预。

## 开发

```bash
# 运行测试
pytest

# 代码检查
ruff check .

# 类型检查
mypy src/

# 格式化代码
ruff format .
```

## API 文档

本地直接运行后端默认访问 http://localhost:11001/docs；通过 `./compose.sh` 启动时默认从网关访问 http://localhost:11000/docs。
