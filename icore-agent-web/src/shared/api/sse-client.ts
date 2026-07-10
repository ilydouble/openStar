import {
  buildApiUrl,
  buildFirstPartyHeaders,
  createRequestId,
  emitHttpTrace,
  normalizeFetchError,
  readFetchResponse,
  type ApiHeaders,
} from './api-client'

export interface SseRequestOptions<TBody = unknown> {
  method?: 'GET' | 'POST'
  body?: TBody
  headers?: ApiHeaders
  signal?: AbortSignal
}

/** Open a first-party SSE response without buffering, retrying, or imposing a timeout. */
export async function openSseResponse<TBody = unknown>(
  path: string,
  options: SseRequestOptions<TBody> = {},
): Promise<Response> {
  const requestId = createRequestId()
  const method = options.method || 'GET'
  const url = buildApiUrl(path)
  const startedAt = now()
  const initialHeaders: HeadersInit = {
    Accept: 'text/event-stream',
    'Cache-Control': 'no-cache',
    ...options.headers,
  }
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    initialHeaders['Content-Type'] = 'application/json'
  }
  const headers = buildFirstPartyHeaders(initialHeaders, { requestId })

  emitHttpTrace({ phase: 'request', requestId, method, url, attempt: 0 })
  try {
    const response = await fetch(url, {
      method,
      headers,
      body: serializeBody(options.body),
      cache: 'no-store',
      signal: options.signal,
    })
    if (!response.ok) await readFetchResponse(response)
    emitHttpTrace({
      phase: 'success',
      requestId: response.headers.get('X-Request-ID') || requestId,
      method,
      url,
      attempt: 0,
      status: response.status,
      durationMs: Math.max(0, Math.round(now() - startedAt)),
    })
    return response
  } catch (error) {
    const normalized = normalizeFetchError(error, { requestId, requestUrl: url })
    if (normalized.name !== 'AbortError') {
      emitHttpTrace({
        phase: 'error',
        requestId,
        method,
        url,
        attempt: 0,
        status: 'status' in normalized ? Number(normalized.status) : undefined,
        durationMs: Math.max(0, Math.round(now() - startedAt)),
        errorCode: 'errorCode' in normalized ? String(normalized.errorCode) : undefined,
      })
    }
    throw normalized
  }
}

/** Serialize supported SSE request bodies without touching binary or form payloads. */
function serializeBody(body: unknown): BodyInit | null | undefined {
  if (body === undefined || body === null) return body
  if (body instanceof FormData || body instanceof Blob || typeof body === 'string') return body
  return JSON.stringify(body)
}

/** Return a monotonic timestamp where the runtime provides one. */
function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}
