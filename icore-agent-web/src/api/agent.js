const BASE = '/api/v1/agent'

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
  // 4–8 字：打字感好，marked 重跑成本可接受
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
 */
export async function* chatStream(message, sessionId, agentHint = '') {
  const resp = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      stream: true,
      agent_hint: agentHint || '',
    }),
    // 提示运行时尽量不把整段体缓冲完再交给我们（对浏览器/部分代理仅作软提示）
    cache: 'no-store',
  })

  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${await resp.text()}`)
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      stream: false,
      agent_hint: agentHint || '',
    }),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/**
 * 执行序列化任务（mini-SWE-agent）
 */
export async function runSequential(task, useDocker = false) {
  const resp = await fetch(`${BASE}/sequential`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task, use_docker: useDocker }),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/**
 * 清除会话记忆
 */
export async function clearSession(sessionId) {
  const resp = await fetch(`${BASE}/session/${sessionId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 生成随机 session id */
export function newSessionId() {
  return crypto.randomUUID()
}

// ── 附件管理 ──────────────────────────────────────────────────────────────

/**
 * 上传文件并附加到会话上下文
 * @param {File} file
 * @param {string} sessionId
 * @returns {Promise<{filename: string, char_count: number, mode: string}>}
 */
export async function attachFile(file, sessionId) {
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', sessionId)
  const resp = await fetch(`${BASE}/attach`, { method: 'POST', body: form })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(detail.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/**
 * 上传图片（jpg/png/webp 等）并附加到会话上下文
 * @param {File} file
 * @param {string} sessionId
 * @returns {Promise<{filename: string, ref: string, size: number, mode: string}>}
 */
export async function attachImage(file, sessionId) {
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', sessionId)
  const resp = await fetch(`${BASE}/attach/image`, { method: 'POST', body: form })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(detail.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/**
 * 上传结构化数据文件（.csv / .xlsx / .xls）并落盘到 data_agent 可读的 workspace
 * @param {File} file
 * @param {string} sessionId
 * @returns {Promise<{filename: string, ref: string, size: number, ext: string,
 *   row_count: number|null, columns: Array<{name:string,dtype:string}>,
 *   preview_md: string, preview_error: string, mode: string}>}
 */
export async function attachData(file, sessionId) {
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', sessionId)
  const resp = await fetch(`${BASE}/attach/data`, { method: 'POST', body: form })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(detail.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 给一个会话内的图片 ref（形如 `{session_id}/{filename}`）构造前端可访问的 URL */
export function imageUrl(ref) {
  if (!ref) return ''
  if (/^https?:\/\//i.test(ref)) return ref
  return `${BASE}/images/${ref}`
}

/**
 * 列出当前会话的附件（不含文本内容）
 * @param {string} sessionId
 * @returns {Promise<Array<{filename: string, char_count: number, mode: string, uploaded_at: number}>>}
 */
export async function listAttachments(sessionId) {
  const resp = await fetch(`${BASE}/attachments/${sessionId}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/**
 * 删除指定附件
 * @param {string} sessionId
 * @param {string} filename
 */
export async function removeAttachment(sessionId, filename) {
  const resp = await fetch(
    `${BASE}/attachments/${sessionId}/${encodeURIComponent(filename)}`,
    { method: 'DELETE' },
  )
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}
