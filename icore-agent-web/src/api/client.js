import { buildAuthHeaders } from '../auth/session.js'

/**
 * Read a fetch response as JSON when possible and surface backend error detail consistently.
 * @param {Response} resp
 * @returns {Promise<any>}
 */
export async function readJsonResponse(resp) {
  const contentType = resp.headers.get('content-type') || ''
  let payload = null
  let detail = ''

  try {
    if (contentType.includes('application/json')) {
      payload = await resp.json()
      detail = String(payload?.detail || payload?.message || '').trim()
    } else {
      detail = String(await resp.text()).trim()
    }
  } catch {
    payload = null
    detail = ''
  }

  if (!resp.ok) {
    throw new Error(detail ? `HTTP ${resp.status}: ${detail}` : `HTTP ${resp.status}`)
  }
  return payload
}

/**
 * Build a tiny JSON-first HTTP client so domain API modules stop duplicating fetch boilerplate.
 * @param {{ getAccessToken?: () => string, fetchImpl?: typeof fetch }} [options]
 */
export function createJsonClient(options = {}) {
  const fetchImpl = options.fetchImpl || fetch
  const getAccessToken = options.getAccessToken || (() => '')

  async function request(path, init = {}) {
    const headers = buildAuthHeaders(
      {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers || {}),
      },
      getAccessToken,
    )
    const resp = await fetchImpl(path, {
      ...init,
      headers,
    })
    return readJsonResponse(resp)
  }

  return {
    request,
    get(path, init = {}) {
      return request(path, init)
    },
    post(path, body, init = {}) {
      return request(path, {
        ...init,
        method: 'POST',
        body: JSON.stringify(body),
      })
    },
    delete(path, init = {}) {
      return request(path, {
        ...init,
        method: 'DELETE',
      })
    },
  }
}
