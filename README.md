# iCore Agent Platform

企业级智能代理平台，基于 Strands Agents 和 LiteLLM 构建，提供深度研究、代码开发、知识库问答等 AI 能力。

## ✨ 功能特性

### 🤖 智能代理
- **研究助手** - 多源网络检索、事实交叉验证、结构化研究报告生成
- **代码工程师** - 编写、审查、调试代码，支持序列化 bash 任务执行
- **知识问答** - 从企业内部文档中精准检索并生成有据可查的答案

### 🛠️ 工具集
- 网络搜索（Tavily / DDG）
- API 调用（支持 REST API）
- 代码执行（Python 沙箱）
- 文件操作（读写文件）
- 序列化任务（mini-SWE 风格逐步执行）

### 🌐 模型支持
- Anthropic Claude
- OpenAI GPT
- Google Gemini
- Z.AI / 智谱 GLM（包括 GLM-4.7）
- 本地 Ollama
- 其他 LiteLLM 支持的模型

### 🌍 国际化
- 支持中文/英文切换
- 前端全页面国际化
- 语言设置持久化

## 🏗️ 技术栈

### 后端 (icore-agent)
- **Python 3.11+**
- **FastAPI** - Web 框架
- **Strands Agents** - Agent 框架
- **LiteLLM** - 统一 LLM 调用接口
- **Redis** - 对话记忆存储
- **Pydantic** - 数据验证

### 前端 (icore-agent-web)
- **Vue 3** - 前端框架
- **Vite** - 构建工具
- **Vue Router** - 路由管理
- **Vue I18n** - 国际化
- **Tailwind CSS** - 样式框架

## 📦 安装

### 后端安装

```bash
cd icore-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"

# 复制环境变量配置
cp .env.example .env

# 编辑 .env 文件，配置你的模型和 API Key
```

### 前端安装

```bash
cd icore-agent-web

# 安装依赖
npm install
```

## ⚙️ 配置

### 后端配置 (.env)

```bash
# 主力模型配置
MODEL_ID=zai/glm-4.7  # 或 anthropic/claude-sonnet-4-5, openai/gpt-4o 等

# Z.AI / 智谱 GLM 配置（使用 zai/* 模型时需要）
ZAI_API_KEY=your-api-key-here
ZAI_API_BASE=https://open.bigmodel.cn/api/paas/v4

# 其他 Provider API Key
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=...

# Agent 配置
AGENT_MAX_TOKENS=8192
AGENT_TEMPERATURE=0.1

# Redis 配置
REDIS_URL=redis://localhost:6379/0
MEMORY_TTL_SECONDS=86400

# 工具配置
TAVILY_API_KEY=your-tavily-api-key
```

## 🚀 运行

### 启动后端

```bash
cd icore-agent
source venv/bin/activate  # 激活虚拟环境

# 开发模式
icore-agent

# 或使用 uvicorn 直接运行
uvicorn icore_agent.main:app --reload --host 0.0.0.0 --port 8080
```

后端将在 http://localhost:8080 启动

### 启动前端

```bash
cd icore-agent-web

# 开发模式
npm run dev
```

前端将在 http://localhost:5173 启动

### 使用 Docker

```bash
# 启动 Redis
docker-compose up -d redis

# 启动后端
docker-compose up -d agent

# 启动前端
docker-compose up -d web
```

## 📁 项目结构

```
iCore/
├── icore-agent/                 # 后端服务
│   ├── src/icore_agent/
│   │   ├── api/                # API 路由
│   │   ├── config/             # 配置管理
│   │   ├── engine/             # Agent 引擎
│   │   │   ├── agents/         # 子 Agent（研究、代码、知识）
│   │   │   ├── sequential/     # 序列化任务执行器
│   │   │   └── orchestrator.py # 主协调器
│   │   ├── tools/              # 工具函数
│   │   └── main.py             # 应用入口
│   ├── tests/                  # 测试
│   ├── pyproject.toml          # 项目配置
│   └── .env                    # 环境变量
│
└── icore-agent-web/             # 前端应用
    ├── src/
    │   ├── components/         # 组件
    │   │   ├── AppNavbar.vue   # 导航栏
    │   │   ├── ChatPanel.vue   # 聊天面板
    │   │   ├── SearchBar.vue   # 搜索栏
    │   │   └── ...
    │   ├── views/              # 页面
    │   │   ├── HomeView.vue    # 首页
    │   │   └── ChatView.vue    # 聊天页
    │   ├── locales/            # 国际化文件
    │   │   ├── zh-CN.js        # 中文
    │   │   └── en-US.js        # 英文
    │   ├── i18n/               # i18n 配置
    │   ├── api/                # API 调用
    │   └── main.js             # 应用入口
    ├── package.json            # 项目配置
    └── tailwind.config.js      # Tailwind 配置
```

## 🔌 API 文档

启动后端服务后，访问 http://localhost:8080/docs 查看 Swagger API 文档。

### 主要 API 端点

- `POST /api/v1/chat/completions` - 聊天对话（SSE 流式）
- `POST /api/v1/agent/research` - 研究助手
- `POST /api/v1/agent/code` - 代码助手
- `POST /api/v1/agent/knowledge` - 知识问答
- `POST /api/v1/agent/sequential/run` - 序列化任务执行

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 Apache-2.0 许可证。详见 [LICENSE](LICENSE) 文件。

## 📧 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。

---

**星纬智能 AI** - Enterprise Intelligence Platform
