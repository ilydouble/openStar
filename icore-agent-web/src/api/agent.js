const BASE = '/api/v1/agent'

/**
 * 流式对话 — 返回 AsyncGenerator，逐 token yield 文本片段
 * @param {string} message
 * @param {string} sessionId
 */
export async function* chatStream(message, sessionId) {
  const resp = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, stream: true }),
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
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6).trim()
      if (payload === '[DONE]') return
      try {
        const token = JSON.parse(payload)
        if (typeof token === 'string' && token.startsWith('[ERROR]')) throw new Error(token)
        yield token
      } catch (e) {
        if (e.message.startsWith('[ERROR]')) throw e
        // JSON 解析失败则原样输出（兼容旧格式）
        yield payload
      }
    }
  }
}

/**
 * 非流式对话（备用）
 */
export async function chat(message, sessionId) {
  const resp = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, stream: false }),
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
