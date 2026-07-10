import { buildAuthHeaders, getAccessToken } from '../../auth/session'
import { authTrace } from '../../auth/trace'
import i18n from '../i18n'

/** HTTP statuses that always map to localized copy instead of backend detail. */
const LOCALIZED_STATUS_CODES = new Set([401, 403, 404, 500])

/**
 * Build a user-facing API error message without an HTTP status prefix.
 */
export function formatApiErrorMessage(status: number, detail = '', requestUrl = ''): string {
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
    return t(keyByStatus[status as keyof typeof keyByStatus])
  }
  const trimmed = String(detail || '').trim()
  if (trimmed) return trimmed
  return t('errors.generic')
}

/**
 * Read a fetch response as JSON when possible and surface backend error detail consistently.
 */
export async function readJsonResponse(resp: Response): Promise<unknown> {
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
    Object.assign(err, { status: resp.status, detail })
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
 */
export interface JsonClientOptions {
  getAccessToken?: () => string
  fetchImpl?: typeof fetch
}

export type JsonRequestInit = Omit<RequestInit, 'body'> & {
  body?: BodyInit | null
}

export interface JsonClient {
  request(path: string | URL, init?: JsonRequestInit): Promise<unknown>
  get(path: string | URL, init?: JsonRequestInit): Promise<unknown>
  post(path: string | URL, body: unknown, init?: JsonRequestInit): Promise<unknown>
  put(path: string | URL, body: unknown, init?: JsonRequestInit): Promise<unknown>
  delete(path: string | URL, init?: JsonRequestInit): Promise<unknown>
}

/** Create a JSON-first HTTP client with consistent auth and response handling. */
export function createJsonClient(options: JsonClientOptions = {}): JsonClient {
  const fetchImpl = options.fetchImpl || fetch
  const readToken = options.getAccessToken ?? getAccessToken

  async function request(path: string | URL, init: JsonRequestInit = {}): Promise<unknown> {
    const headers = buildAuthHeaders(
      {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers as Record<string, string> | undefined),
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
    get(path: string | URL, init: JsonRequestInit = {}) {
      return request(path, init)
    },
    post(path: string | URL, body: unknown, init: JsonRequestInit = {}) {
      return request(path, {
        ...init,
        method: 'POST',
        body: JSON.stringify(body),
      })
    },
    put(path: string | URL, body: unknown, init: JsonRequestInit = {}) {
      return request(path, {
        ...init,
        method: 'PUT',
        body: JSON.stringify(body),
      })
    },
    delete(path: string | URL, init: JsonRequestInit = {}) {
      return request(path, {
        ...init,
        method: 'DELETE',
      })
    },
  }
}
