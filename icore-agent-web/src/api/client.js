import { buildAuthHeaders, getAccessToken } from '../auth/session'
import { authTrace } from '../auth/trace'
import i18n from '../i18n'

/** HTTP statuses that always map to localized copy instead of backend detail. */
const LOCALIZED_STATUS_CODES = new Set([401, 403, 404, 500])

/**
 * Build a user-facing API error message without an HTTP status prefix.
 * @param {number} status
 * @param {string} [detail]
 * @param {string} [requestUrl]
 * @returns {string}
 */
export function formatApiErrorMessage(status, detail = '', requestUrl = '') {
  const t = i18n.global.t.bind(i18n.global)
  if (LOCALIZED_STATUS_CODES.has(status)) {
    if (status === 404 && String(requestUrl).includes('/api/v1/account/')) {
      return t('auth.emailNotRegistered')
    }
    const keyByStatus = {
      401: 'errors.http401',
      403: 'errors.http403',
      404: 'errors.http404',
      500: 'errors.http500',
    }
    return t(keyByStatus[status])
  }
  const trimmed = String(detail || '').trim()
  if (trimmed) return trimmed
  return t('errors.generic')
}

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
    const err = new Error(
      formatApiErrorMessage(resp.status, detail, resp.url || ''),
    )
    err.status = resp.status
    err.detail = detail
    throw err
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
