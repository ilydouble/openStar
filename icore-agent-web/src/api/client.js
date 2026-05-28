import { buildAuthHeaders, getAccessToken } from '../auth/session.js'
import { authTrace } from '../auth/trace.js'

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
  if (
    payload &&
    typeof payload === 'object' &&
    Object.prototype.hasOwnProperty.call(payload, 'code') &&
    Object.prototype.hasOwnProperty.call(payload, 'message') &&
    Object.prototype.hasOwnProperty.call(payload, 'data') &&
    Object.prototype.hasOwnProperty.call(payload, 'timestamp')
  ) {
    return payload.data
  }
  return payload
}

/**
 * Build a tiny JSON-first HTTP client so domain API modules stop duplicating fetch boilerplate.
 * Sends `Authorization: Bearer <token>` using {@link getAccessToken} from session storage unless
 * `getAccessToken` is overridden (e.g. in tests).
 * @param {{ getAccessToken?: () => string, fetchImpl?: typeof fetch }} [options]
 */
export function createJsonClient(options = {}) {
  const fetchImpl = options.fetchImpl || fetch
  const readToken = options.getAccessToken ?? getAccessToken

  async function request(path, init = {}) {
    const headers = buildAuthHeaders(
      {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers || {}),
      },
      readToken,
    )
    const method = (init.method || 'GET').toUpperCase()
    const tokenViaReader = typeof readToken === 'function' ? readToken() : ''
    authTrace(`${method} JSON client`, {
      url: typeof path === 'string' ? path : String(path),
      authorizationScheme: headers.Authorization ? 'Bearer' : '(missing)',
      tokenLengthFromReader: typeof tokenViaReader === 'string' ? tokenViaReader.length : -1,
    })
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
    put(path, body, init = {}) {
      return request(path, {
        ...init,
        method: 'PUT',
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
