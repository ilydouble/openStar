import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosInstance,
  type AxiosRequestConfig,
} from 'axios'
import axiosRetry from 'axios-retry'

import i18n from '../i18n'

const DEFAULT_API_BASE_URL = '/api/v1'
const DEFAULT_API_TIMEOUT_MS = 15_000
const DEFAULT_FILE_TIMEOUT_MS = 120_000
const DEFAULT_RETRY_COUNT = 2
const MAX_RETRY_COUNT = 5
const RETRYABLE_STATUS_CODES = new Set([408, 429, 502, 503, 504])
const RETRYABLE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
const LOCALIZED_STATUS_CODES = new Set([401, 403, 404, 500])

export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  timestamp: string
  error_code?: string
}

export type ApiMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'HEAD' | 'OPTIONS'
export type ApiHeaders = Record<string, string>
export type ApiQueryValue = string | number | boolean | null | undefined
export type ApiQuery = Record<string, ApiQueryValue | ApiQueryValue[]>

export interface ApiRequestOptions {
  headers?: ApiHeaders
  params?: ApiQuery
  signal?: AbortSignal
  timeoutMs?: number
  retry?: false | number
}

export interface ApiRequestConfig<TBody = unknown> extends ApiRequestOptions {
  method: ApiMethod
  path: string
  body?: TBody
}

export interface ApiClient {
  request<TResponse, TBody = unknown>(config: ApiRequestConfig<TBody>): Promise<TResponse>
  get<TResponse>(path: string, options?: ApiRequestOptions): Promise<TResponse>
  post<TResponse, TBody = unknown>(
    path: string,
    body?: TBody,
    options?: ApiRequestOptions,
  ): Promise<TResponse>
  put<TResponse, TBody = unknown>(
    path: string,
    body?: TBody,
    options?: ApiRequestOptions,
  ): Promise<TResponse>
  delete<TResponse>(path: string, options?: ApiRequestOptions): Promise<TResponse>
}

export type HttpTracePhase = 'request' | 'success' | 'retry' | 'error'

export interface HttpTraceEvent {
  phase: HttpTracePhase
  requestId: string
  method: string
  url: string
  attempt: number
  status?: number
  durationMs?: number
  errorCode?: string
}

export type HttpTraceSink = (event: HttpTraceEvent) => void
export type TokenReader = () => string

export interface ApiClientConfiguration {
  tokenReader: TokenReader
  traceSink?: HttpTraceSink
}

export interface CreateApiClientOptions {
  baseURL?: string
  timeoutMs?: number
  retryCount?: number
  retryDelayMs?: number
  tokenReader?: TokenReader
  requestIdFactory?: () => string
  traceSink?: HttpTraceSink
  adapter?: AxiosAdapter
}

interface RequestTraceMetadata {
  requestId: string
  startedAt: number
}

declare module 'axios' {
  interface AxiosRequestConfig {
    icoreTrace?: RequestTraceMetadata
  }
}

/** Normalized error exposed at the shared HTTP boundary. */
export class ApiError extends Error {
  status: number
  errorCode: string
  detail: string
  data: unknown
  requestId: string
  retryable: boolean

  constructor({
    message,
    status = 0,
    errorCode = '',
    detail = '',
    data = null,
    requestId = '',
    retryable = false,
    cause,
  }: {
    message: string
    status?: number
    errorCode?: string
    detail?: string
    data?: unknown
    requestId?: string
    retryable?: boolean
    cause?: unknown
  }) {
    super(message, cause === undefined ? undefined : { cause })
    this.name = 'ApiError'
    this.status = status
    this.errorCode = errorCode
    this.detail = detail
    this.data = data
    this.requestId = requestId
    this.retryable = retryable
  }
}

let configuredTokenReader: TokenReader = () => ''
let configuredTraceSink: HttpTraceSink | undefined

/** Configure browser-specific authentication and optional trace delivery at app startup. */
export function configureApiClient({ tokenReader, traceSink }: ApiClientConfiguration): void {
  configuredTokenReader = tokenReader
  configuredTraceSink = traceSink
}

/** Read the access token configured by the application bootstrap. */
export function readConfiguredAccessToken(): string {
  const token = configuredTokenReader()
  return typeof token === 'string' ? token : ''
}

/** Return the public API base URL, including the `/api/v1` prefix. */
export function getApiBaseUrl(): string {
  return normalizeBaseUrl(readEnvString('VITE_PUBLIC_API_BASE_URL') || DEFAULT_API_BASE_URL)
}

/** Build a first-party API URL for fetch-based transports. */
export function buildApiUrl(path: string, baseURL = getApiBaseUrl()): string {
  if (/^[a-z][a-z\d+.-]*:\/\//i.test(path) || path.startsWith('//')) return path
  return `${normalizeBaseUrl(baseURL)}/${path.replace(/^\/+/, '')}`
}

/** Return the configured timeout for ordinary API requests. */
export function getApiTimeoutMs(): number {
  return readBoundedInteger('VITE_API_TIMEOUT_MS', DEFAULT_API_TIMEOUT_MS, 1, 600_000)
}

/** Return the configured timeout for uploads and speech transcription. */
export function getFileTimeoutMs(): number {
  return readBoundedInteger('VITE_FILE_TIMEOUT_MS', DEFAULT_FILE_TIMEOUT_MS, 1, 3_600_000)
}

/** Return the configured number of retries after the initial attempt. */
export function getApiRetryCount(): number {
  return readBoundedInteger('VITE_API_RETRY_COUNT', DEFAULT_RETRY_COUNT, 0, MAX_RETRY_COUNT)
}

/** Generate one correlation id for a logical request and all of its retry attempts. */
export function createRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

/** Apply shared first-party headers without exposing token values to logs. */
export function buildFirstPartyHeaders(
  initial: HeadersInit = {},
  {
    requestId = createRequestId(),
    tokenReader = readConfiguredAccessToken,
  }: { requestId?: string; tokenReader?: TokenReader } = {},
): Headers {
  const headers = new Headers(initial)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  if (!headers.has('X-Request-ID')) headers.set('X-Request-ID', requestId)
  const token = tokenReader()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return headers
}

/** Emit sanitized HTTP trace metadata to the configured sink or development console. */
export function emitHttpTrace(event: HttpTraceEvent, sink = configuredTraceSink): void {
  if (sink) {
    sink(event)
    return
  }
  if (isHttpTracingEnabled()) console.debug('[icore-http]', event)
}

/** Build a user-facing API error message without an HTTP status prefix. */
export function formatApiErrorMessage(status: number, detail = '', requestUrl = ''): string {
  const t = i18n.global.t.bind(i18n.global)
  if (LOCALIZED_STATUS_CODES.has(status)) {
    if (status === 404 && /\/account\//.test(String(requestUrl))) {
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
  return trimmed || t('errors.generic')
}

/** Unwrap the repository-wide API envelope while accepting non-envelope payloads. */
export function unwrapApiPayload<T>(payload: unknown): T {
  if (isApiEnvelope<T>(payload)) return payload.data
  return payload as T
}

/** Read a fetch response using the same envelope and error contract as Axios. */
export async function readFetchResponse<T>(response: Response): Promise<T> {
  const payload = await readResponsePayload(response)
  if (!response.ok) {
    throw apiErrorFromPayload({
      status: response.status,
      payload,
      requestUrl: response.url,
      requestId: response.headers.get('X-Request-ID') || '',
    })
  }
  return unwrapApiPayload<T>(payload)
}

/** Convert an unknown transport failure into the shared cancellation or API error shape. */
export function normalizeFetchError(
  error: unknown,
  { requestId = '', requestUrl = '' }: { requestId?: string; requestUrl?: string } = {},
): Error {
  if (isAbortError(error)) return createAbortError(error)
  if (error instanceof ApiError) return error
  return new ApiError({
    message: i18n.global.t('errors.network'),
    detail: error instanceof Error ? error.message : String(error || ''),
    requestId,
    retryable: true,
    cause: error,
  })
}

/** Create a typed client around one isolated Axios instance. */
export function createApiClient(options: CreateApiClientOptions = {}): ApiClient {
  const baseURL = normalizeBaseUrl(options.baseURL || getApiBaseUrl())
  const timeout = normalizePositiveInteger(options.timeoutMs, getApiTimeoutMs())
  const retryCount = normalizeRetryCount(options.retryCount, getApiRetryCount())
  const retryDelayMs = normalizePositiveInteger(options.retryDelayMs, 250, true)
  const tokenReader = options.tokenReader || readConfiguredAccessToken
  const requestIdFactory = options.requestIdFactory || createRequestId
  const traceSink = options.traceSink

  const instance = axios.create({
    baseURL,
    timeout,
    adapter: options.adapter,
  })

  configureRetries(instance, retryCount, retryDelayMs, traceSink)
  configureInterceptors(instance, tokenReader, requestIdFactory, traceSink)

  /** Send one request and return its unwrapped business payload. */
  async function request<TResponse, TBody = unknown>(
    config: ApiRequestConfig<TBody>,
  ): Promise<TResponse> {
    const retry = config.retry === false
      ? 0
      : normalizeRetryCount(config.retry, retryCount)
    const response = await instance.request<ApiEnvelope<TResponse> | TResponse>({
      method: config.method,
      url: config.path,
      data: config.body,
      headers: config.headers,
      params: config.params,
      signal: config.signal,
      timeout: normalizePositiveInteger(config.timeoutMs, timeout),
      'axios-retry': { retries: retry },
    })
    return unwrapApiPayload<TResponse>(response.data)
  }

  return {
    request,
    get<TResponse>(path: string, requestOptions: ApiRequestOptions = {}) {
      return request<TResponse>({ method: 'GET', path, ...requestOptions })
    },
    post<TResponse, TBody = unknown>(
      path: string,
      body?: TBody,
      requestOptions: ApiRequestOptions = {},
    ) {
      return request<TResponse, TBody>({ method: 'POST', path, body, ...requestOptions })
    },
    put<TResponse, TBody = unknown>(
      path: string,
      body?: TBody,
      requestOptions: ApiRequestOptions = {},
    ) {
      return request<TResponse, TBody>({ method: 'PUT', path, body, ...requestOptions })
    },
    delete<TResponse>(path: string, requestOptions: ApiRequestOptions = {}) {
      return request<TResponse>({ method: 'DELETE', path, ...requestOptions })
    },
  }
}

/** Attach the conservative retry policy to an isolated Axios instance. */
function configureRetries(
  instance: AxiosInstance,
  retryCount: number,
  retryDelayMs: number,
  traceSink?: HttpTraceSink,
): void {
  axiosRetry(instance, {
    retries: retryCount,
    shouldResetTimeout: true,
    retryCondition(error) {
      const method = String(error.config?.method || '').toUpperCase()
      if (!RETRYABLE_METHODS.has(method) || axios.isCancel(error)) return false
      if (!error.response) return true
      return RETRYABLE_STATUS_CODES.has(error.response.status)
    },
    retryDelay(retryNumber, error) {
      return axiosRetry.exponentialDelay(retryNumber, error, retryDelayMs)
    },
    onRetry(retryNumber, error, config) {
      const metadata = config.icoreTrace
      emitHttpTrace({
        phase: 'retry',
        requestId: metadata?.requestId || '',
        method: String(config.method || 'GET').toUpperCase(),
        url: buildRequestUrl(config),
        attempt: retryNumber,
        status: error.response?.status,
        errorCode: error.code,
      }, traceSink)
    },
  })
}

/** Attach authentication, correlation, trace, and error interceptors. */
function configureInterceptors(
  instance: AxiosInstance,
  tokenReader: TokenReader,
  requestIdFactory: () => string,
  traceSink?: HttpTraceSink,
): void {
  instance.interceptors.request.use((config) => {
    const headers = AxiosHeaders.from(config.headers)
    const existingRequestId = String(headers.get('X-Request-ID') || '')
    const metadata = config.icoreTrace || {
      requestId: existingRequestId || requestIdFactory(),
      startedAt: now(),
    }
    config.icoreTrace = metadata
    if (!headers.has('Accept')) headers.set('Accept', 'application/json')
    if (!headers.has('X-Request-ID')) headers.set('X-Request-ID', metadata.requestId)
    const token = tokenReader()
    if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
    config.headers = headers

    emitHttpTrace({
      phase: 'request',
      requestId: metadata.requestId,
      method: String(config.method || 'GET').toUpperCase(),
      url: buildRequestUrl(config),
      attempt: config['axios-retry']?.retryCount || 0,
    }, traceSink)
    return config
  })

  instance.interceptors.response.use(
    (response) => {
      const metadata = response.config.icoreTrace
      emitHttpTrace({
        phase: 'success',
        requestId: readAxiosHeader(response.headers, 'X-Request-ID') || metadata?.requestId || '',
        method: String(response.config.method || 'GET').toUpperCase(),
        url: buildRequestUrl(response.config),
        attempt: response.config['axios-retry']?.retryCount || 0,
        status: response.status,
        durationMs: metadata ? Math.max(0, Math.round(now() - metadata.startedAt)) : undefined,
      }, traceSink)
      return response
    },
    (error: unknown) => {
      const normalized = normalizeAxiosError(error)
      if (normalized.name !== 'AbortError') {
        const config = axios.isAxiosError(error) ? error.config : undefined
        const metadata = config?.icoreTrace
        const apiError = normalized instanceof ApiError ? normalized : null
        emitHttpTrace({
          phase: 'error',
          requestId: apiError?.requestId || metadata?.requestId || '',
          method: String(config?.method || 'GET').toUpperCase(),
          url: config ? buildRequestUrl(config) : '',
          attempt: config?.['axios-retry']?.retryCount || 0,
          status: apiError?.status || undefined,
          durationMs: metadata ? Math.max(0, Math.round(now() - metadata.startedAt)) : undefined,
          errorCode: apiError?.errorCode || (axios.isAxiosError(error) ? error.code : undefined),
        }, traceSink)
      }
      return Promise.reject(normalized)
    },
  )
}

/** Normalize an Axios failure without leaking Axios-specific errors to features. */
function normalizeAxiosError(error: unknown): Error {
  if (axios.isCancel(error)) return createAbortError(error)
  if (!axios.isAxiosError(error)) {
    if (error instanceof Error) return error
    return new ApiError({ message: i18n.global.t('errors.generic'), cause: error })
  }

  const response = error.response
  const config = error.config
  const metadata = config?.icoreTrace
  if (!response) {
    const timedOut = error.code === AxiosError.ECONNABORTED || error.code === AxiosError.ETIMEDOUT
    return new ApiError({
      message: i18n.global.t(timedOut ? 'errors.timeout' : 'errors.network'),
      detail: error.message,
      errorCode: error.code || '',
      requestId: metadata?.requestId || '',
      retryable: true,
      cause: error,
    })
  }

  return apiErrorFromPayload({
    status: response.status,
    payload: response.data,
    requestUrl: config ? buildRequestUrl(config) : '',
    requestId: readAxiosHeader(response.headers, 'X-Request-ID') || metadata?.requestId || '',
    cause: error,
  })
}

/** Build a shared API error from an HTTP status and backend payload. */
function apiErrorFromPayload({
  status,
  payload,
  requestUrl,
  requestId,
  cause,
}: {
  status: number
  payload: unknown
  requestUrl: string
  requestId: string
  cause?: unknown
}): ApiError {
  const record = isRecord(payload) ? payload : null
  const detail = readString(record?.detail) || readString(record?.message) || readString(payload)
  const errorCode = readString(record?.error_code)
  return new ApiError({
    message: formatApiErrorMessage(status, detail, requestUrl),
    status,
    errorCode,
    detail,
    data: record?.data ?? null,
    requestId,
    retryable: RETRYABLE_STATUS_CODES.has(status),
    cause,
  })
}

/** Return whether a payload follows the repository-wide API envelope contract. */
function isApiEnvelope<T>(payload: unknown): payload is ApiEnvelope<T> {
  if (!isRecord(payload)) return false
  return ['code', 'message', 'data', 'timestamp'].every((key) => key in payload)
}

/** Parse a fetch response as JSON when declared, otherwise as text. */
async function readResponsePayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  try {
    if (contentType.includes('application/json')) return await response.json()
    return await response.text()
  } catch {
    return null
  }
}

/** Combine one Axios request URL with its configured base URL. */
function buildRequestUrl(config: AxiosRequestConfig): string {
  const path = String(config.url || '')
  if (/^[a-z][a-z\d+.-]*:\/\//i.test(path) || path.startsWith('//')) return path
  return buildApiUrl(path, String(config.baseURL || getApiBaseUrl()))
}

/** Normalize a base URL to a non-empty value without a trailing slash. */
function normalizeBaseUrl(value: string): string {
  return String(value || DEFAULT_API_BASE_URL).trim().replace(/\/+$/, '') || DEFAULT_API_BASE_URL
}

/** Clamp retry counts to the supported client range. */
function normalizeRetryCount(value: number | undefined, fallback: number): number {
  if (!Number.isFinite(value)) return fallback
  return Math.min(Math.max(Math.trunc(value as number), 0), MAX_RETRY_COUNT)
}

/** Normalize a positive integer while optionally accepting zero. */
function normalizePositiveInteger(
  value: number | undefined,
  fallback: number,
  allowZero = false,
): number {
  if (!Number.isFinite(value)) return fallback
  const normalized = Math.trunc(value as number)
  return normalized >= (allowZero ? 0 : 1) ? normalized : fallback
}

/** Read and clamp an integer-valued Vite environment setting. */
function readBoundedInteger(name: string, fallback: number, min: number, max: number): number {
  const value = readEnvString(name)
  if (!value) return fallback
  const raw = Number(value)
  if (!Number.isFinite(raw)) return fallback
  return Math.min(Math.max(Math.trunc(raw), min), max)
}

/** Read one string-valued Vite environment setting safely in browser and tests. */
function readEnvString(name: string): string {
  const env = import.meta.env as unknown as Record<string, unknown> | undefined
  const value = env?.[name]
  return typeof value === 'string' ? value.trim() : ''
}

/** Return whether sanitized HTTP tracing is enabled for this build. */
function isHttpTracingEnabled(): boolean {
  const env = import.meta.env as unknown as Record<string, unknown> | undefined
  return env?.DEV === true || env?.VITE_DEBUG_HTTP === 'true'
}

/** Narrow an unknown value to a non-array object record. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

/** Normalize an optional payload field to trimmed text. */
function readString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

/** Read one Axios response header regardless of its runtime header representation. */
function readAxiosHeader(headers: unknown, name: string): string {
  if (headers instanceof AxiosHeaders) return String(headers.get(name) || '')
  if (!isRecord(headers)) return ''
  const target = name.toLowerCase()
  const key = Object.keys(headers).find((candidate) => candidate.toLowerCase() === target)
  return key ? String(headers[key] || '') : ''
}

/** Return whether a transport error represents caller cancellation. */
function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

/** Preserve the fetch-compatible AbortError contract across Axios cancellation. */
function createAbortError(cause: unknown): Error {
  if (typeof DOMException !== 'undefined') {
    return new DOMException('The operation was aborted.', 'AbortError')
  }
  const error = new Error('The operation was aborted.', { cause })
  error.name = 'AbortError'
  return error
}

/** Return a monotonic timestamp where the runtime provides one. */
function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

export const apiClient = createApiClient()
