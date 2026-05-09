# iCore Agent Backend

基于 FastAPI 和 Strands Agents 的后端服务，提供企业级 AI 代理能力。

## 功能特性

- 🤖 多 Agent 协调（研究、代码、知识库）
- 🛠️ 丰富的工具集成（搜索、API 调用、代码执行、文件操作）
- 🔄 流式响应（SSE）
- 🌐 多模型支持（通过 LiteLLM）
- 💾 对话记忆（Redis）
- 🔒 可配置的认证

## 快速开始

```bash
# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
for file in dotenv/.env.*.example; do cp "$file" "${file%.example}"; done
# 编辑 dotenv/.env.llm 配置你的 API Key

# 启动服务
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

环境变量按业务域拆分到 `dotenv/.env.{domain}`，模板文件为
`dotenv/.env.{domain}.example`。真实 `.env.{domain}` 文件只用于本地运行，不提交。

## Docker Compose

```bash
./compose.sh up -d --build
./compose.sh logs -f icore-agent
```

`compose.sh` 会自动为 Docker Compose 加载所有分域环境变量文件。

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

本地直接运行默认访问 http://localhost:8080/docs；通过 `./compose.sh` 启动时默认访问 http://localhost:10001/docs。
