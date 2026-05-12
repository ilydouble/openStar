# iCore Agent 后端接口文档

> 服务实现：`icore-agent/src/icore_agent/api/routers/`
> 入口：`icore_agent.main:app`（FastAPI / Uvicorn）

## 基础约定

| 项 | 值 |
|---|---|
| Base URL | `http://{host}:{port}`（默认 `0.0.0.0:8080`） |
| Agent 前缀 | `/api/v1/agent` |
| Knowledge 前缀 | `/api/v1/knowledge` |
| 认证 | `settings.auth_enabled=True` 时由 `AuthMiddleware` 接管，默认关闭 |
| 交互式文档 | `debug=True` 时开放 `/docs`、`/redoc` |
| 多租户 | 通过 `tenant_code`（form 字段或 query 参数）隔离知识库集合 |

所有请求体 / 响应体均为 UTF-8 JSON，除非显式说明为 `multipart/form-data` 或 `text/event-stream`。

## 1. 健康检查

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | Liveness，返回 `{status, version, service}` |
| GET | `/ready` | Readiness，预留给下游组件连通性检查 |

## 2. Agent 会话 —— `/api/v1/agent/chat`

主入口。一次请求完成一轮"理解 → 路由 → 子 agent 执行 → 合成回复"。

### 2.1 Request

`POST /api/v1/agent/chat`

```json
{
  "message": "帮我对比 GPT-5 和 Claude Opus 4 的架构差异",
  "session_id": "b3d4...",
  "stream": true,
  "agent_hint": "research",
  "tenant_code": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `message` | string | ✓ | 用户输入，1–32000 字符 |
| `session_id` | string | ✗ | 省略则服务器生成 UUID；同一会话共享短期记忆 + 附件 |
| `stream` | bool | ✗ | 默认 `true`，走 SSE；`false` 为阻塞式 JSON 响应 |
| `agent_hint` | string | ✗ | 强制路由到指定子 agent。合法值：`research` / `code` / `knowledge` / `image` / `data` / `chat`。留空则由规则分类器自动判定 |
| `tenant_code` | string | ✗ | 多租户隔离标识 |

### 2.2 SSE 协议（`stream=true`）

响应头：`Content-Type: text/event-stream`、`Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`、`Connection: keep-alive`、`X-Session-Id: {session_id}`。

每一帧格式 `data: {JSON}\n\n`。事件类型：

| type | payload | 含义 |
|---|---|---|
| `status` | `{step:N, tool, input_preview}` | 工具/子 agent 开始执行。`step` 自 1 递增 |
| `token` | `{text}` | LLM 流式 token 增量 |
| `error` | `{message}` | 失败（包括墙钟预算超时） |
| `done` | `{}` | 本轮结束；紧接着一条 `data: [DONE]\n\n` |

另外每 **15 秒** 静默会插入一条 `: keep-alive\n\n` 注释帧用于保活。单轮墙钟预算 **600 秒**，超过会推一条 `error` 并关闭流。

**最小客户端示例**（JS）：

```js
const resp = await fetch('/api/v1/agent/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message, session_id, stream: true, agent_hint: 'research' }),
})
const reader = resp.body.getReader()
const dec = new TextDecoder()
let buf = ''
while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buf += dec.decode(value, { stream: true })
  const lines = buf.split('\n'); buf = lines.pop()
  for (const line of lines) {
    if (line.startsWith(':') || !line.startsWith('data: ')) continue
    const p = line.slice(6).trim()
    if (p === '[DONE]') return
    const e = JSON.parse(p)
    // e.type: 'status' | 'token' | 'error' | 'done'
  }
}
```

`curl` 调试：

```bash
curl -N -H "Content-Type: application/json" \
  -d '{"message":"hi","session_id":"t1","stream":true}' \
  http://localhost:8080/api/v1/agent/chat
```

### 2.3 非流式（`stream=false`）

同一端点，阻塞直到结束：

```json
{ "session_id": "b3d4...", "reply": "..." }
```

### 2.4 路由决策逻辑（简述）

1. `agent_hint` 合法时直接生效：`chat` 禁用全部工具；其它值强制启用对应子 agent
2. 否则由规则分类器 `_classify_intent` 判定 `chat` / `task`
3. 如会话挂载了 RAG 文档 / 图片 / 数据文件，自动启用工具

## 3. 会话管理

`DELETE /api/v1/agent/session/{session_id}` — 清空对话记忆 + 所有附件。

```json
{ "cleared": true, "session_id": "b3d4..." }
```

## 4. 附件 —— 按会话挂载

附件与 `session_id` 绑定：一旦挂载，该会话后续 `chat` 请求会自动让 orchestrator 看到它们（文档进入 inline 上下文或 RAG，图片/数据文件作为 refs 交给对应子 agent）。

### 4.1 文档 —— `POST /api/v1/agent/attach`

`multipart/form-data`：

| 字段 | 说明 |
|---|---|
| `file` | `.pdf` / `.docx` / `.txt` / `.md`，大小上限 `file_ops_max_size_mb` |
| `session_id` | 目标会话 |

返回：`{filename, char_count, mode}`。`mode` 为 `inline` 或 `rag`，由文本长度自动决定。

### 4.2 图片 —— `POST /api/v1/agent/attach/image`

| 字段 | 说明 |
|---|---|
| `file` | `.jpg` / `.jpeg` / `.png` / `.webp` / `.bmp` / `.gif`，上限 `image_upload_max_mb` |
| `session_id` | 目标会话 |

返回：`{filename, ref, size, mode: "image"}`。`ref` 形如 `{session_id}/{filename}`。

图片访问：`GET /api/v1/agent/images/{session_id}/{filename}` → 原始二进制。

### 4.3 结构化数据 —— `POST /api/v1/agent/attach/data`

| 字段 | 说明 |
|---|---|
| `file` | `.csv` / `.xlsx` / `.xls`，上限 `data_upload_max_mb` |
| `session_id` | 目标会话 |

返回包含行数、列 schema、markdown 预览，可直接展示给用户：

```json
{
  "filename": "sales.csv",
  "ref": "b3d4.../sales.csv",
  "size": 12345,
  "ext": ".csv",
  "row_count": 1024,
  "columns": [{"name": "date", "dtype": "datetime64"}, ...],
  "preview_md": "| date | amount |\n|---|---|\n...",
  "preview_error": "",
  "mode": "data"
}
```

### 4.4 列出 / 删除附件

- `GET /api/v1/agent/attachments/{session_id}` → `AttachmentInfo[]`
- `DELETE /api/v1/agent/attachments/{session_id}/{filename}` → `{removed, filename, session_id}`

## 5. 知识库（租户级共享）—— `/api/v1/knowledge`

与会话附件不同，这里是 **跨会话、按 `tenant_code` 隔离** 的持久 Chroma 集合。

| Method | Path | 说明 |
|---|---|---|
| POST | `/upload` | form: `file` + `tenant_code`（可空）→ 切块 + 入库。响应 `{filename, tenant_code, chunks_stored}` |
| GET | `/documents?tenant_code=` | 列出文档及其分块数 |
| DELETE | `/documents/{filename}?tenant_code=` | 按文件名删除所有分块 |

支持格式：`.pdf` / `.docx` / `.txt` / `.md`，大小上限同文档附件。切块参数来自 `settings.rag_chunk_size` / `rag_chunk_overlap`。

检索入口不在此 router —— 由 `knowledge_agent_tool` 在对话过程中调用 Chroma，客户端只需上传。

## 6. 顺序执行任务 —— `POST /api/v1/agent/sequential`

mini-SWE-agent 风格的"一步一命令"执行器，适合纯 bash 自动化任务。**阻塞返回**，不走 SSE。

```json
// 请求
{ "task": "列出当前目录所有 *.py 文件的行数", "use_docker": false }

// 响应
{ "status": "completed", "output": "...", "steps": 7 }
```

`use_docker=true` 时在隔离容器内执行；否则使用本地 shell（生产慎用）。

## 7. 错误处理

| HTTP | 场景 |
|---|---|
| 400 | 文件名包含路径分隔符等非法输入 |
| 404 | 附件 / 知识库文档 / 图片不存在 |
| 413 | 上传超过 `{file_ops|image_upload|data_upload}_max_size_mb` |
| 415 | 文件扩展名不被支持 |
| 422 | 文件解析失败或内容为空 |
| 500 | 下游异常（LLM / 向量库 / 顺序执行器） |

SSE 流的运行期错误通过 `{"type":"error","message":...}` 事件下发，HTTP 层仍为 200。

## 8. 可观测性

每次 LLM 调用（orchestrator / 子 agent / rolling-summary）都会由 `litellm.success_callback` 输出一条结构化日志：

```
llm_token_usage model=zai/glm-4.7 prompt_tokens=... completion_tokens=... total_tokens=... elapsed_s=...
```

chat 流程中的关键事件：`intent_classified`、`tool_call`、`agent_stream_error`、`agent_stream_wall_timeout`、`attachment_added`、`knowledge_uploaded`。
