import {
  ApiError,
  apiClient,
  createRequestId,
  emitHttpTrace,
  formatApiErrorMessage,
  getFileTimeoutMs,
  normalizeFetchError,
} from '../../../../shared/infrastructure/http/api-client'
import i18n from '../../../../shared/presentation/i18n'

const FILE_BASE = '/files'

export type FileStorageRecord = Record<string, unknown>

export interface FileUploadUrlCommand {
  original_filename: string
  content_type: string
  checksum_sha256: string
}

export interface CompleteFileUploadCommand {
  checksum_sha256: string
}

export interface PresignedUploadOptions {
  contentType: string
  timeoutMs?: number
}

/** Request an authenticated upload URL from the first-party files API. */
export function requestFileUploadUrl<TResponse = FileStorageRecord>(
  command: FileUploadUrlCommand,
): Promise<TResponse> {
  return apiClient.post<TResponse, FileUploadUrlCommand>(`${FILE_BASE}/upload-url/`, command)
}

/** Mark one uploaded storage object complete after checksum verification. */
export function completeFileUpload<TResponse = FileStorageRecord>(
  fileUuid: string,
  command: CompleteFileUploadCommand,
): Promise<TResponse> {
  const encodedUuid = encodeURIComponent(fileUuid)
  return apiClient.post<TResponse, CompleteFileUploadCommand>(
    `${FILE_BASE}/${encodedUuid}/complete/`,
    command,
  )
}

/** Fetch a temporary download URL for one owned file asset. */
export function fetchFileDownloadUrl<TResponse = FileStorageRecord>(
  fileUuid: string,
): Promise<TResponse> {
  return apiClient.get<TResponse>(`${FILE_BASE}/${encodeURIComponent(fileUuid)}/download-url/`)
}

/** Delete one owned file asset through the first-party files API. */
export function deleteFileStorageAsset(fileUuid: string): Promise<unknown> {
  return apiClient.delete(`${FILE_BASE}/${encodeURIComponent(fileUuid)}/`)
}

/** Upload a body to an external presigned URL without first-party auth or correlation headers. */
export async function putPresignedFile(
  uploadUrl: string,
  body: Blob,
  options: PresignedUploadOptions,
): Promise<void> {
  const requestId = createRequestId()
  const method = 'PUT'
  const startedAt = now()
  const timeoutMs = normalizeTimeout(options.timeoutMs)
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort('file_upload_timeout'), timeoutMs)

  emitHttpTrace({ phase: 'request', requestId, method, url: redactUrl(uploadUrl), attempt: 0 })
  try {
    const response = await fetch(uploadUrl, {
      method,
      headers: { 'Content-Type': options.contentType },
      body,
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new ApiError({
        message: formatApiErrorMessage(response.status, '', response.url || uploadUrl),
        status: response.status,
        requestId,
      })
    }
    emitHttpTrace({
      phase: 'success',
      requestId,
      method,
      url: redactUrl(uploadUrl),
      attempt: 0,
      status: response.status,
      durationMs: Math.max(0, Math.round(now() - startedAt)),
    })
  } catch (error) {
    const timedOut = controller.signal.aborted && controller.signal.reason === 'file_upload_timeout'
    const normalized = timedOut
      ? new ApiError({
          message: timeoutMessage(),
          detail: 'file_upload_timeout',
          errorCode: 'ETIMEDOUT',
          requestId,
          retryable: false,
          cause: error,
        })
      : normalizeFetchError(error, { requestId, requestUrl: uploadUrl })
    if (normalized.name !== 'AbortError') {
      emitHttpTrace({
        phase: 'error',
        requestId,
        method,
        url: redactUrl(uploadUrl),
        attempt: 0,
        status: normalized instanceof ApiError ? normalized.status || undefined : undefined,
        durationMs: Math.max(0, Math.round(now() - startedAt)),
        errorCode: normalized instanceof ApiError ? normalized.errorCode || undefined : undefined,
      })
    }
    throw normalized
  } finally {
    clearTimeout(timeoutId)
  }
}

/** Resolve a per-request file timeout against the configured default. */
function normalizeTimeout(value: number | undefined): number {
  return Number.isFinite(value) && Number(value) > 0 ? Math.trunc(Number(value)) : getFileTimeoutMs()
}

/** Remove query credentials from presigned URLs before logging. */
function redactUrl(value: string): string {
  try {
    const url = new URL(value)
    return `${url.origin}${url.pathname}`
  } catch {
    return String(value).split('?')[0]
  }
}

/** Return localized copy for a timed-out file transfer. */
function timeoutMessage(): string {
  return i18n.global.t('errors.fileTimeout')
}

/** Return a monotonic timestamp where the runtime provides one. */
function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}
