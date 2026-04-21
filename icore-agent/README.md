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
cp .env.example .env
# 编辑 .env 配置你的 API Key

# 启动服务
icore-agent
```

## 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| MODEL_ID | 主力模型 ID | anthropic/claude-sonnet-4-5 |
| ZAI_API_KEY | 智谱 API Key | - |
| ZAI_API_BASE | 智谱 API 地址 | https://open.bigmodel.cn/api/paas/v4 |
| ANTHROPIC_API_KEY | Anthropic API Key | - |
| OPENAI_API_KEY | OpenAI API Key | - |
| REDIS_URL | Redis 连接地址 | redis://localhost:6379/0 |
| AGENT_MAX_TOKENS | 最大 token 数 | 8192 |
| AGENT_TEMPERATURE | 温度参数 | 0.1 |

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

启动服务后访问 http://localhost:8080/docs
