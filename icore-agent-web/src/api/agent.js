import { buildAuthHeaders, getAccessToken } from '../auth/session.js'
import { authTrace } from '../auth/trace.js'
import { formatApiErrorMessage, readJsonResponse } from './client.js'

const BASE = '/api/v1/agent'
const FILE_BASE = '/api/v1/files'
const PI_WORKSPACE_BASE = '/api/v1/pi/workspaces'

/**
 * Thrown when the backend returns 402 quota_exceeded.
 * Carries the current plan and the upgrade URL so the UI can show
 * an upgrade modal without needing extra API calls.
 */
export class QuotaExceededError extends Error {
  /**
   * @param {{ current_plan?: string, upgrade_url?: string }} [data]
   */
  constructor(data = {}) {
    super('quota_exceeded')
    this.name = 'QuotaExceededError'
    this.currentPlan = data.current_plan || 'trial'
    this.upgradeUrl = data.upgrade_url || '/pricing'
  }
}

/** Bearer + trace (dev / VITE_DEBUG_AUTH) for outbound agent fetch calls. */
function mergeAgentAuthHeaders(extra = {}, label = 'agent-fetch') {
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
 * @param {Response} resp
 * @returns {Promise<never>}
 */
export async function readAgentError(resp) {
  let payload = null
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
  err.status = resp.status
  err.detail = detail
  throw err
}

/**
 * 后端或代理有时会把整段回复塞进「一条」token。若前端一次性 append，Vue
 * 会合并更新，表现成「唰一下整段出现」。将长串拆成多段 yield，让 for-await
 * 每步都能 await，从而一帧一帧刷新。
 * @param {string} text
 * @yields {{ kind: 'token', text: string }}
 */
function *yieldTokenChunks(text) {
  const t = String(text ?? '')
  if (!t) return
  // Chunk long token bursts so the UI can update incrementally during streaming.
  const SLICE = 30
  if (t.length <= SLICE) {
    yield { kind: 'token', text: t }
    return
  }
  for (let i = 0; i < t.length; i += SLICE) {
    yield { kind: 'token', text: t.slice(i, i + SLICE) }
  }
}

/**
 * 流式对话 — 返回 AsyncGenerator，yield 类型化事件：
 *   { kind: 'token',  text: string }                                        — LLM 流式 token
 *   { kind: 'status', tool: string, input_preview: string, step: number }  — 子 agent 工具开始执行
 *   { kind: 'error',  message: string }                                     — 错误
 *   { kind: 'done' }                                                        — 本轮结束
 *
 * 向后兼容：旧后端如果推送的是裸字符串，会被当作 token 文本处理。
 *
 * @param {string} message
 * @param {string} sessionId
 * @param {string} [agentHint] 可选：research | code | knowledge | image | data | chat
 * @param {{ signal?: AbortSignal }} [options] 传入 signal 可中止 fetch / 流读取（用户点击停止）
 */
export async function* chatStream(message, sessionId, agentHint = '', options = {}) {
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
  // Pi mode: id of the user-uploaded project workspace Pi should analyze.
  // Only meaningful alongside agentHint === 'pi' — backend resolves it through
  // PiWorkspaceService (ownership-checked) and extracts it into a sandbox
  // before pointing the Pi agent at it. Absent → Pi falls back to its
  // default read-only service workspace.
  const piWorkspaceId = typeof options?.piWorkspaceId === 'string'
    ? options.piWorkspaceId.trim()
    : ''
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
      ...(piWorkspaceId ? { pi_workspace_id: piWorkspaceId } : {}),
    }),
    // 提示运行时尽量不把整段体缓冲完再交给我们（对浏览器/部分代理仅作软提示）
    cache: 'no-store',
    signal,
  })

  if (!resp.ok) {
    await readAgentError(resp)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() // 保留未完整的行

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
        // 非 JSON：按裸文本处理
        for (const ev of yieldTokenChunks(payload)) yield ev
        continue
      }

      // 新协议：typed 事件
      if (parsed && typeof parsed === 'object') {
        const type = parsed.type
        if (type === 'token') {
          for (const ev of yieldTokenChunks(String(parsed.text ?? ''))) yield ev
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
        }
        continue
      }

      // 旧协议：裸字符串
      if (typeof parsed === 'string') {
        if (parsed.startsWith('[ERROR]')) throw new Error(parsed)
        for (const ev of yieldTokenChunks(parsed)) yield ev
      }
    }
  }
}

/**
 * 非流式对话（备用）
 */
export async function chat(message, sessionId, agentHint = '') {
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
  return readJsonResponse(resp)
}

/**
 * 执行序列化任务（mini-SWE-agent）
 */
export async function runSequential(task, useDocker = false) {
  const resp = await fetch(`${BASE}/sequential`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ task, use_docker: useDocker }),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * Finalize a session so durable user memory can be extracted without deleting it.
 */
export async function finalizeSession(sessionId) {
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
export async function clearSession(sessionId) {
  const resp = await fetch(`${BASE}/session/${sessionId}`, {
    method: 'DELETE',
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

export async function getSessionState(sessionId) {
  const resp = await fetch(`${BASE}/session/${sessionId}`, {
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * Fetch one page of the user's chat sessions from PostgreSQL.
 * @param {{ limit?: number, offset?: number }} [opts]
 * @returns {Promise<{ sessions: Array, total: number, limit: number, offset: number }>}
 */
export async function fetchSessions(opts = {}) {
  const limit = Math.min(Math.max(Number(opts.limit) || 20, 1), 100)
  const offset = Math.max(Number(opts.offset) || 0, 0)
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const resp = await fetch(`${BASE}/sessions?${qs}`, {
    headers: mergeAgentAuthHeaders(),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * Load every session page until all rows are retrieved (ordered by updated_at desc).
 * @returns {Promise<{ sessions: Array, total: number }>}
 */
export async function fetchAllSessions() {
  const pageSize = 100
  let offset = 0
  let total = 0
  const sessions = []
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
 * @param {string} query
 * @param {{ limit?: number, offset?: number }} [opts]
 * @returns {Promise<{ query: string, sessions: Array, total: number, limit: number, offset: number }>}
 */
export async function searchSessions(query, opts = {}) {
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
  return readJsonResponse(resp)
}

/** 生成随机 session id */
export function newSessionId() {
  return crypto.randomUUID()
}

// ── 文件资产管理 ──────────────────────────────────────────────────────────

/**
 * 计算文件的 SHA-256。
 * @param {File} file
 * @returns {Promise<string>}
 */
async function sha256File(file) {
  const buffer = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

/**
 * 上传用户文件资产：申请 URL、直传 storage-service、complete 校验。
 * @param {File} file
 * @returns {Promise<{file_uuid: string, original_filename: string, filename: string,
 *   content_type: string, storage_etag: string|null, mode: string, download_url?: string}>}
 */
export async function uploadFileAsset(file) {
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
  const upload = await readJsonResponse(uploadResp)

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
  const completed = await readJsonResponse(completeResp)

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

/**
 * Bütün layihə qovluğunu (File[] - webkitdirectory ilə seçilmiş) zip arxivinə
 * sıxır. Toxunulmamış halda saxlanılır (DEFLATE 0) ki, brauzerdə tez işləsin —
 * tam sıxılma serverdə arxivi inspektə edərkən artıq edilmir, server tərəfdə
 * checksum/limit/path-traversal yoxlamaları zəruri qoruma qatıdır.
 * @param {File[]} files - `webkitRelativePath` daşıyan fayllar
 * @returns {Promise<{ blob: Blob, fileCount: number }>}
 */
async function zipProjectFiles(files) {
  const { default: JSZip } = await import('jszip')
  const zip = new JSZip()
  let fileCount = 0
  for (const file of files) {
    const relPath = file.webkitRelativePath || file.name
    if (!relPath) continue
    zip.file(relPath, file)
    fileCount += 1
  }
  const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } })
  return { blob, fileCount }
}

/**
 * SHA-256 hesabla (Blob üçün) — sha256File ilə eyni alqoritm, fərqli giriş tipi.
 * @param {Blob} blob
 * @returns {Promise<string>}
 */
async function sha256Blob(blob) {
  const buffer = await blob.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

/**
 * Pi mode üçün bütün layihə qovluğunu yükləyir: client-side zip → presigned URL
 * → birbaşa MinIO-ya PUT → complete (checksum + sandbox təhlükəsizlik yoxlaması).
 * Mirrors `uploadFileAsset`'s presign/PUT/complete flow 1:1, only the bucket
 * and verification differ (server validates the zip's internal structure too).
 * @param {File[]} files - `<input webkitdirectory multiple>` ilə seçilmiş fayllar
 * @param {string} title - layihənin görünən adı (məs. kök qovluğun adı)
 * @param {(progress: {stage: string, loaded?: number, total?: number}) => void} [onProgress]
 * @returns {Promise<{id: string, title: string, status: string, size_bytes: number,
 *   file_count: number, created_at: number, updated_at: number}>}
 */
export async function uploadPiProjectFolder(files, title, onProgress) {
  if (!files?.length) throw new Error('No files selected')

  onProgress?.({ stage: 'zipping' })
  const { blob, fileCount } = await zipProjectFiles(files)
  const checksum = await sha256Blob(blob)

  onProgress?.({ stage: 'requesting-url' })
  const urlResp = await fetch(`${PI_WORKSPACE_BASE}/upload-url/`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }, 'pi-workspace-upload-url'),
    body: JSON.stringify({
      title: (title || '').slice(0, 200) || 'Untitled project',
      checksum_sha256: checksum,
    }),
  })
  if (!urlResp.ok) await readAgentError(urlResp)
  const upload = await readJsonResponse(urlResp)

  onProgress?.({ stage: 'uploading', total: blob.size })
  const putResp = await fetch(upload.upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/zip' },
    body: blob,
  })
  if (!putResp.ok) {
    throw new Error(formatApiErrorMessage(putResp.status, '', putResp.url || ''))
  }

  onProgress?.({ stage: 'verifying' })
  const completeResp = await fetch(`${PI_WORKSPACE_BASE}/${encodeURIComponent(upload.workspace_id)}/complete/`, {
    method: 'POST',
    headers: mergeAgentAuthHeaders({ 'Content-Type': 'application/json' }, 'pi-workspace-complete'),
    body: JSON.stringify({ checksum_sha256: checksum }),
  })
  if (!completeResp.ok) await readAgentError(completeResp)
  const completed = await readJsonResponse(completeResp)

  onProgress?.({ stage: 'done' })
  return { ...completed, file_count: completed.file_count ?? fileCount }
}

/**
 * Cari istifadəçinin Pi mode üçün yüklədiyi layihələrin siyahısını qaytarır.
 * @returns {Promise<Array<{id: string, title: string, status: string, size_bytes: number,
 *   file_count: number, created_at: number, updated_at: number}>>}
 */
export async function listPiWorkspaces() {
  const resp = await fetch(`${PI_WORKSPACE_BASE}/`, {
    headers: mergeAgentAuthHeaders({}, 'pi-workspace-list'),
  })
  if (!resp.ok) await readAgentError(resp)
  const payload = await readJsonResponse(resp)
  return payload.workspaces || []
}

/**
 * Bir Pi layihəsini (öz workspace-ini) silir — soft-delete + storage təmizliyi.
 * @param {string} workspaceId
 */
export async function deletePiWorkspace(workspaceId) {
  const resp = await fetch(`${PI_WORKSPACE_BASE}/${encodeURIComponent(workspaceId)}/`, {
    method: 'DELETE',
    headers: mergeAgentAuthHeaders({}, 'pi-workspace-delete'),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

function assetMode(filename, contentType) {
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
 * @param {string} fileUuid
 */
export async function getFileDownloadUrl(fileUuid) {
  const resp = await fetch(`${FILE_BASE}/${encodeURIComponent(fileUuid)}/download-url/`, {
    headers: mergeAgentAuthHeaders({}, 'files-download-url'),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * 删除文件资产。
 * @param {string} fileUuid
 */
export async function deleteFileAsset(fileUuid) {
  const resp = await fetch(`${FILE_BASE}/${encodeURIComponent(fileUuid)}/`, {
    method: 'DELETE',
    headers: mergeAgentAuthHeaders({}, 'files-delete'),
  })
  if (!resp.ok) await readAgentError(resp)
  return readJsonResponse(resp)
}

/**
 * Transcribe microphone audio via backend Z.AI GLM-ASR proxy.
 * @param {Blob} audioBlob
 * @param {{ language?: string, signal?: AbortSignal, filename?: string }} [opts]
 * @returns {Promise<string>}
 */
export async function transcribeSpeech(audioBlob, opts = {}) {
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
  const payload = await readJsonResponse(resp)
  const text = typeof payload?.text === 'string' ? payload.text.trim() : ''
  return text
}
