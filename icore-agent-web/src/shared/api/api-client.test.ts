import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type InternalAxiosRequestConfig,
} from 'axios'

import {
  ApiError,
  createApiClient,
  getApiRetryCount,
  getApiTimeoutMs,
  getFileTimeoutMs,
  type HttpTraceEvent,
} from './api-client'

test('API environment defaults remain active when optional variables are absent', () => {
  assert.equal(getApiTimeoutMs(), 15_000)
  assert.equal(getFileTimeoutMs(), 120_000)
  assert.equal(getApiRetryCount(), 2)
})

test('api client applies base URL, timeout, auth, request id, and envelope unwrapping', async () => {
  let seenConfig: InternalAxiosRequestConfig | undefined
  const traces: HttpTraceEvent[] = []
  const adapter: AxiosAdapter = async (config) => {
    seenConfig = config
    return response(config, 200, envelope({ ok: true }), {
      'X-Request-ID': 'server-request-id',
    })
  }
  const client = createApiClient({
    adapter,
    baseURL: 'https://api.example.test/api/v1/',
    timeoutMs: 9_000,
    tokenReader: () => 'secret-token',
    requestIdFactory: () => 'client-request-id',
    traceSink: (event) => traces.push(event),
  })

  const payload = await client.post<{ ok: boolean }, { hello: string }>(
    '/account/test',
    { hello: 'world' },
  )

  assert.deepEqual(payload, { ok: true })
  assert.equal(seenConfig?.baseURL, 'https://api.example.test/api/v1')
  assert.equal(seenConfig?.timeout, 9_000)
  assert.equal(header(seenConfig, 'Authorization'), 'Bearer secret-token')
  assert.equal(header(seenConfig, 'X-Request-ID'), 'client-request-id')
  assert.deepEqual(traces.map((event) => event.phase), ['request', 'success'])
  assert.equal(traces[1].requestId, 'server-request-id')
  assert.equal('body' in traces[0], false)
  assert.equal('token' in traces[0], false)
})

test('api client converts envelope failures into ApiError metadata', async () => {
  const adapter: AxiosAdapter = async (config) => {
    throw httpError(config, 422, {
      code: 422,
      message: 'invalid command',
      data: { field: 'email' },
      timestamp: '2026-07-10T00:00:00Z',
      error_code: 'validation_error',
    }, { 'X-Request-ID': 'request-422' })
  }
  const client = createApiClient({ adapter, retryDelayMs: 0 })

  await assert.rejects(
    () => client.post('/account/test', { invalid: true }),
    (error) => {
      assert.ok(error instanceof ApiError)
      assert.equal(error.status, 422)
      assert.equal(error.message, 'invalid command')
      assert.equal(error.errorCode, 'validation_error')
      assert.equal(error.requestId, 'request-422')
      assert.deepEqual(error.data, { field: 'email' })
      return true
    },
  )
})

test('api client retries safe requests and preserves their logical request id', async () => {
  let attempts = 0
  const requestIds: string[] = []
  const traces: HttpTraceEvent[] = []
  const adapter: AxiosAdapter = async (config) => {
    attempts += 1
    requestIds.push(header(config, 'X-Request-ID'))
    if (attempts < 3) throw networkError(config)
    return response(config, 200, envelope({ attempt: attempts }))
  }
  const client = createApiClient({
    adapter,
    retryCount: 2,
    retryDelayMs: 0,
    requestIdFactory: () => 'stable-request-id',
    traceSink: (event) => traces.push(event),
  })

  const payload = await client.get<{ attempt: number }>('/agent/sessions')

  assert.deepEqual(payload, { attempt: 3 })
  assert.equal(attempts, 3)
  assert.deepEqual(requestIds, ['stable-request-id', 'stable-request-id', 'stable-request-id'])
  assert.deepEqual(
    traces.filter((event) => event.phase === 'retry').map((event) => event.attempt),
    [1, 2],
  )
})

test('api client never retries unsafe methods by default', async () => {
  let attempts = 0
  const adapter: AxiosAdapter = async (config) => {
    attempts += 1
    throw networkError(config)
  }
  const client = createApiClient({ adapter, retryCount: 2, retryDelayMs: 0 })

  await assert.rejects(() => client.post('/agent/sequential', { task: 'test' }), ApiError)
  assert.equal(attempts, 1)
})

test('api client allows one safe request to disable retries', async () => {
  let attempts = 0
  const adapter: AxiosAdapter = async (config) => {
    attempts += 1
    throw networkError(config)
  }
  const client = createApiClient({ adapter, retryCount: 2, retryDelayMs: 0 })

  await assert.rejects(() => client.get('/agent/sessions', { retry: false }), ApiError)
  assert.equal(attempts, 1)
})

test('api client retries configured transient HTTP statuses for safe methods', async () => {
  let attempts = 0
  const adapter: AxiosAdapter = async (config) => {
    attempts += 1
    if (attempts === 1) {
      throw httpError(config, 429, { detail: 'slow down' }, { 'Retry-After': '0' })
    }
    return response(config, 200, envelope({ ok: true }))
  }
  const client = createApiClient({ adapter, retryCount: 1, retryDelayMs: 0 })

  assert.deepEqual(await client.get('/account/me'), { ok: true })
  assert.equal(attempts, 2)
})

/** Build one successful Axios adapter response. */
function response(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown,
  headers: Record<string, string> = {},
) {
  return {
    config,
    status,
    statusText: String(status),
    data,
    headers: new AxiosHeaders(headers),
  }
}

/** Build the backend's shared success envelope. */
function envelope<T>(data: T) {
  return {
    code: 200,
    message: 'ok',
    data,
    timestamp: '2026-07-10T00:00:00Z',
  }
}

/** Build an Axios HTTP error as a custom adapter would return it. */
function httpError(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown,
  headers: Record<string, string> = {},
) {
  return new AxiosError(
    `Request failed with status ${status}`,
    AxiosError.ERR_BAD_RESPONSE,
    config,
    undefined,
    response(config, status, data, headers),
  )
}

/** Build a retryable network error without an HTTP response. */
function networkError(config: InternalAxiosRequestConfig) {
  return new AxiosError('network unavailable', AxiosError.ERR_NETWORK, config)
}

/** Read one normalized request header from an Axios config. */
function header(config: InternalAxiosRequestConfig | undefined, name: string): string {
  if (!config) return ''
  return String(AxiosHeaders.from(config.headers).get(name) || '')
}
