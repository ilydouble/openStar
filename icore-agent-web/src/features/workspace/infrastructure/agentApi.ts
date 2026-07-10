import { buildAuthHeaders, getAccessToken } from '../../auth/application/session'
import { authTrace } from '../../auth/application/trace'
import { formatApiErrorMessage, readJsonResponse } from '../../../shared/api/client'

const BASE = '/api/v1/agent'
const FILE_BASE = '/api/v1/files'

type AnyRecord = Record<string, any>
type HeaderBag = Record<string, string>

export interface QuotaExceededData {
  current_plan?: string
  upgrade_url?: string
}

export interface ChatStreamOptions {
  signal?: AbortSignal
  fileUuids?: string[]
  displayCaption?: string
  agentMessage?: string
  templateId?: string
  incognito?: boolean
}

export interface PageOptions {
  limit?: number
  offset?: number
}

export interface SessionSearchResult {
  query: string
  sessions: AnyRecord[]
  total: number
  limit: number
  offset: number
}

/**
 * Thrown when the backend returns 402 quota_exceeded.
 * Carries the current plan and the upgrade URL so the UI can show
 * an upgrade modal without needing extra API calls.
 */
export class QuotaExceededError extends Error {
  currentPlan: string
  upgradeUrl: string

  constructor(data: QuotaExceededData = {}) {
    super('quota_exceeded')
    this.name = 'QuotaExceededError'
    this.currentPlan = data.current_plan || 'trial'
    this.upgradeUrl = data.upgrade_url || '/pricing'
  }
}

/** Bearer + trace (dev / VITE_DEBUG_AUTH) for outbound agent fetch calls. */
function mergeAgentAuthHeaders(extra: HeaderBag = {}, label = 'agent-fetch'): HeaderBag {
  const token = getAccessToken()
  const sessionTokenLen = typeof token === 'string' ? token.length : -1
  const headers = buildAuthHeaders(extra)
  authTrace(label, {
    hasBearer: Boolean(headers.Authorization),
    sessionTokenLength: sessionTokenLen,
  })
  return headers
}

/**
 * Parse an agent API error response.
 *
 * Returns 402 quota_exceeded as a typed QuotaExceededError so callers
 * can show an upgrade modal instead of a generic error message.
 * All other non-ok responses become a plain Error with HTTP status info.
 *
 */
export async function readAgentError(resp: Response): Promise<never> {
  let payload: AnyRecord | null = null
  try {
    const ct = resp.headers.get('content-type') || ''
    if (ct.includes('application/json')) {
      payload = await resp.json()
    }
  } catch {
    // ignore parse failures — fall through to generic error
  }

  if (resp.status === 402 && payload?.error_code === 'quota_exceeded') {
    throw new QuotaExceededError(payload?.data || {})
  }

  const detail = String(payload?.detail || payload?.message || '').trim()
  const err = new Error(
    formatApiErrorMessage(resp.status, detail, resp.url || ''),
  )
    Object.assign(err, { status: resp.status, detail })
  throw err
}

/**
 * 后端或代理有时会把整段回复塞进「一条」token。若前端一次性 append，Vue
 * 会合并更新，表现成「唰一下整段出现」。将长串拆成多段 yield，让 for-await
 * 每步都能 await，从而一帧一帧刷新。
 */
function *yieldTokenChunks(text: string): Generator<{ kind: 'token'; text: string }> {
  const t = String(text ?? '')
  if (!t) return
  // Chunk long token bursts so the UI can update incrementally during streaming.
  const SLICE = 6
  if (t.length <= SLICE) {
    yield { kind: 'token', text: t }
    return
  }
  for (let i = 0; i < t.length; i += SLICE) {
    yield { kind: 'token', text: t.slice(i, i + SLICE) }
  }
}

/**
 * Open the backend streaming chat response for one turn request.
 */
async function openChatStreamResponse(
  message: string,
  sessionId: string,
  agentHint = '',
  options: ChatStreamOptions = {},
): Promise<Response> {
  const signal = options && options.signal
  const fileUuids = Array.isArray(options?.fileUuids) ? options.fileUuids : []
  const displayCaption = typeof options?.displayCaption === 'string'
    ? options.displayCaption.trim()
    : ''
  const agentMessage = typeof options?.agentMessage === 'string'
    ? options.agentMessage.trim()
    : ''
  const templateId = typeof options?.templateId === 'string'
    ? options.templateId.trim()
    : ''
  const incognito = Boolean(options?.incognito)
  const resp = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message,
      session_id: sessionId,
      stream: true,
      agent_hint: agentHint || '',
      file_uuids: fileUuids,
      ...(displayCaption ? { display_caption: displayCaption } : {}),
      ...(agentMessage ? { agent_message: agentMessage } : {}),
      ...(templateId ? { template_id: templateId } : {}),
      ...(incognito ? { incognito: true } : {}),
    }),
    // 提示运行时尽量不把整段体缓冲完再交给我们（对浏览器/部分代理仅作软提示）
    cache: 'no-store',
    signal,
  })

  if (!resp.ok) {
    await readAgentError(resp)
  }
  return resp
}

/**
 * Stream raw backend turn events without flattening them into token/status rows.
 *
 */
export async function* chatEventStream(
  message: string,
  sessionId: string,
  agentHint = '',
  options: ChatStreamOptions = {},
): AsyncGenerator<AnyRecord> {
  const resp = await openChatStreamResponse(message, sessionId, agentHint, options)
  if (!resp.body) {
    throw new Error('Streaming response body is empty')
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? '' // 保留未完整的行

    for (const line of lines) {
      // SSE comment（心跳）以 ':' 开头；本协议里用于 keep-alive，前端可忽略
      if (line.startsWith(':')) continue
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6).trim()
      if (payload === '[DONE]') return

      let parsed
      try {
        parsed = JSON.parse(payload)
      } catch {
        // 旧协议裸文本：转成最小 raw token event，调用方再决定如何投影。
        yield { type: 'token', text: payload }
        continue
      }

      // 新协议：原样暴露 typed turn event。
      if (parsed && typeof parsed === 'object') {
        yield parsed
        if (parsed.type === 'done') return
        continue
      }

      // 旧协议：裸字符串
      if (typeof parsed === 'string') {
        if (parsed.startsWith('[ERROR]')) {
          yield { type: 'error', message: parsed }
        } else {
          yield { type: 'token', text: parsed }
        }
      }
    }
  }
}

/**
 * 流式对话兼容层 — 返回 AsyncGenerator，yield 类型化事件：
 *   { kind: 'token',  text: string }                                        — LLM 流式 token
 *   { kind: 'status', tool: string, input_preview: string, step: number }  — 工具开始执行
 *   { kind: 'error',  message: string }                                     — 错误
 *   { kind: 'done' }                                                        — 本轮结束
 *
 * 新 UI 应使用 chatEventStream()，此函数仅保留旧 token/status 消费者。
 *
 */
export async function* chatStream(
  message: string,
  sessionId: string,
  agentHint = '',
  options: ChatStreamOptions = {},
): AsyncGenerator<AnyRecord> {
  let receivedAssistantText = false

  for await (const parsed of chatEventStream(message, sessionId, agentHint, options)) {
    if (!parsed || typeof parsed !== 'object') continue
    const type = parsed.type
    if (type === 'token') {
      for (const ev of yieldTokenChunks(String(parsed.text ?? ''))) {
        receivedAssistantText = true
        yield ev
      }
    } else if (type === 'status') {
      yield {
        kind: 'status',
        tool: String(parsed.tool ?? ''),
        input_preview: String(parsed.input_preview ?? ''),
        step: Number(parsed.step ?? 0),
      }
    } else if (type === 'error') {
      throw new Error(String(parsed.message ?? 'unknown error'))
    } else if (type === 'done') {
      return
    } else if (type === 'item_delta') {
      const text = String(parsed.delta?.text_append ?? parsed.delta?.text ?? '')
      for (const ev of yieldTokenChunks(text)) {
        receivedAssistantText = true
        yield ev
      }
    } else if (type === 'item_started') {
      const status = parseTurnItemStatus(parsed.item)
      if (status) yield status
    } else if (type === 'item_completed') {
      const item = parsed.item
      if (!receivedAssistantText && item?.type === 'agent_message') {
        for (const ev of yieldTokenChunks(String(item.text ?? ''))) {
          receivedAssistantText = true
          yield ev
        }
      }
    } else if (type === 'turn_completed') {
      if (!receivedAssistantText) {
        for (const ev of yieldTokenChunks(String(parsed.reply ?? ''))) {
          receivedAssistantText = true
          yield ev
        }
      }
      return
    } else if (type === 'turn_failed') {
      throw new Error(parseTurnErrorMessage(parsed.error))
    } else if (type === 'turn_aborted') {
      return
    }
  }
}

function parseTurnItemStatus(item: AnyRecord | null | undefined): AnyRecord | null {
  if (!item || item.type !== 'tool_call') return null
  const functionPayload = item.function || {}
  const argsText = String(functionPayload.arguments_text || '').trim()
  const argsJson = functionPayload.arguments_json
  let inputPreview = argsText
  if (!inputPreview && argsJson && typeof argsJson === 'object') {
    try {
      inputPreview = JSON.stringify(argsJson)
    } catch {
      inputPreview = ''
    }
  }
  return {
    kind: 'status',
    tool: String(functionPayload.name || ''),
    input_preview: inputPreview,
    step: Number(item.index ?? 0),
  }
}

function parseTurnErrorMessage(error: AnyRecord | null | undefined): string {
  if (!error || typeof error !== 'object') return 'Agent turn failed'
  return String(error.message || error.code || 'Agent turn failed')
}

/**
 * 非流式对话（备用）
 */
export async function chat(message: string, sessionId: string, agentHint = ''): Promise<unknown> {
  const resp = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message,
      session_id: sessionId,
      stream: false,
      agent_hint: agentHint || '',
    }),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp) as Promise<AnyRecord>
}

/**
 * 执行序列化任务（mini-SWE-agent）
 */
export async function runSequential(task: string, useDocker = false): Promise<unknown> {
  const resp = await fetch(`${BASE}/sequential`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ task, use_docker: useDocker }),
  })
  if (!resp.ok) await readAgentError(resp)
  return await readJsonResponse(resp) as AnyRecord
}

/**
 * Finalize a session so durable user memory can be extracted without deleting it.
 */
export async function finalizeSession(sessionId: string): Promise<unknown> {
  const resp = await fetch(`${BASE}/session/${sessionId}/finalize`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * 清除会话记忆
 */
export async function clearSession(sessionId: string): Promise<unknown> {
  const resp = await fetch(`${BASE}/session/${sessionId}`, {
    method: 'DELETE',
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

export async function getSessionState(sessionId: string): Promise<unknown> {
  const resp = await fetch(`${BASE}/session/${sessionId}`, {
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * Fetch one page of the user's chat sessions from PostgreSQL.
 */
export async function fetchSessions(opts: PageOptions = {}): Promise<AnyRecord> {
  const limit = Math.min(Math.max(Number(opts.limit) || 20, 1), 100)
  const offset = Math.max(Number(opts.offset) || 0, 0)
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const resp = await fetch(`${BASE}/sessions?${qs}`, {
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  const payload = await readJsonResponse(resp)
  return payload as AnyRecord
}

/**
 * Load every session page until all rows are retrieved (ordered by updated_at desc).
 */
export async function fetchAllSessions(): Promise<{ sessions: AnyRecord[]; total: number }> {
  const pageSize = 100
  let offset = 0
  let total = 0
  const sessions: AnyRecord[] = []
  while (true) {
    const payload = await fetchSessions({ limit: pageSize, offset })
    const page = Array.isArray(payload.sessions) ? payload.sessions : []
    total = Number(payload.total ?? 0)
    sessions.push(...page)
    offset += page.length
    if (page.length === 0 || offset >= total) break
  }
  return { sessions, total }
}

/**
 * Search owned chat sessions by title and message content.
 */
export async function searchSessions(query: string, opts: PageOptions = {}): Promise<SessionSearchResult> {
  const q = String(query || '').trim()
  if (!q) {
    return { query: '', sessions: [], total: 0, limit: 20, offset: 0 }
  }
  const limit = Math.min(Math.max(Number(opts.limit) || 20, 1), 100)
  const offset = Math.max(Number(opts.offset) || 0, 0)
  const qs = new URLSearchParams({ q, limit: String(limit), offset: String(offset) })
  const resp = await fetch(`${BASE}/sessions/search?${qs}`, {
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp) as Promise<SessionSearchResult>
}

/** 生成随机 session id */
export function newSessionId(): string {
  return crypto.randomUUID()
}

// ── 文件资产管理 ──────────────────────────────────────────────────────────

/**
 * 计算文件的 SHA-256。
 */
async function sha256File(file: File): Promise<string> {
  const buffer = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

/**
 * 上传用户文件资产：申请 URL、直传 storage-service、complete 校验。
 */
export async function uploadFileAsset(file: File): Promise<AnyRecord> {
  const contentType = file.type || 'application/octet-stream'
  const checksum = await sha256File(file)
  const uploadResp = await fetch(`${FILE_BASE}/upload-url/`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }, 'files-upload-url'),
    body: JSON.stringify({
      original_filename: file.name || 'upload',
      content_type: contentType,
      checksum_sha256: checksum,
    }),
  })
  if (!uploadResp.ok) await readAgentError(uploadResp)
  const upload = await readJsonResponse(uploadResp) as AnyRecord

  const putResp = await fetch(upload.upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': contentType },
    body: file,
  })
  if (!putResp.ok) {
    throw new Error(formatApiErrorMessage(putResp.status, '', putResp.url || ''))
  }

  const completeResp = await fetch(`${FILE_BASE}/${upload.file_uuid}/complete/`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }, 'files-complete'),
    body: JSON.stringify({ checksum_sha256: checksum }),
  })
  if (!completeResp.ok) await readAgentError(completeResp)
  const completed = await readJsonResponse(completeResp) as AnyRecord

  let downloadUrl = ''
  if (contentType.startsWith('image/')) {
    try {
      const download = await getFileDownloadUrl(upload.file_uuid)
      downloadUrl = download.download_url
    } catch {
      downloadUrl = ''
    }
  }

  return {
    ...completed,
    filename: completed.original_filename,
    mode: assetMode(file.name || '', contentType),
    download_url: downloadUrl,
  }
}

function assetMode(filename: string, contentType: string): string {
  const lower = filename.toLowerCase()
  if (contentType.startsWith('image/')) return 'image'
  if (
    lower.endsWith('.csv')
    || lower.endsWith('.xlsx')
    || lower.endsWith('.xls')
    || lower.endsWith('.pdf')
    || lower.endsWith('.doc')
    || lower.endsWith('.docx')
    || lower.endsWith('.txt')
    || lower.endsWith('.md')
  ) return 'data'
  return 'file'
}

/**
 * 获取文件下载 URL。
 */
export async function getFileDownloadUrl(fileUuid: string): Promise<AnyRecord> {
  const resp = await fetch(`${FILE_BASE}/${encodeURIComponent(fileUuid)}/download-url/`, {
    headers: mergeAgentAuthHeaders({}, 'files-download-url'),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp) as Promise<AnyRecord>
}

/**
 * 删除文件资产。
 */
export async function deleteFileAsset(fileUuid: string): Promise<unknown> {
  const resp = await fetch(`${FILE_BASE}/${encodeURIComponent(fileUuid)}/`, {
    method: 'DELETE',
    headers: mergeAgentAuthHeaders({}, 'files-delete'),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * Transcribe microphone audio via backend Z.AI GLM-ASR proxy.
 */
export async function transcribeSpeech(
  audioBlob: Blob,
  opts: { language?: string; signal?: AbortSignal; filename?: string } = {},
): Promise<string> {
  const { language = '', signal, filename = 'recording.webm' } = opts
  const form = new FormData()
  form.append('file', audioBlob, filename)
  if (language) form.append('language', language)

  const resp = await fetch(`${BASE}/transcribe`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({}, 'agent-transcribe'),
    body: form,
    cache: 'no-store',
    signal,
  })
  const payload = await readJsonResponse(resp) as AnyRecord
  const text = typeof payload?.text === 'string' ? payload.text.trim() : ''
  return text
}
