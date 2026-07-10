import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import { AxiosHeaders, type AxiosAdapter } from 'axios'

import {
  ApiError,
  configureApiClient,
  createApiClient,
  type HttpTraceEvent,
} from './api-client'
import {
  completeFileUpload,
  deleteFileStorageAsset,
  fetchFileDownloadUrl,
  putPresignedFile,
  requestFileUploadUrl,
} from './file-storage-client'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
  configureApiClient({ tokenReader: () => '' })
})

test('file metadata operations share the authenticated first-party API client', async () => {
  const calls: Array<{ method: string; path: string; authorization: string }> = []
  const adapter: AxiosAdapter = async (config) => {
    calls.push({
      method: String(config.method || '').toUpperCase(),
      path: String(config.url || ''),
      authorization: String(AxiosHeaders.from(config.headers).get('Authorization') || ''),
    })
    return {
      config,
      status: 200,
      statusText: 'OK',
      data: envelope({ ok: true }),
      headers: new AxiosHeaders(),
    }
  }
  configureApiClient({
    tokenReader: () => 'file-token',
    client: createApiClient({ adapter, tokenReader: () => 'file-token' }),
  })

  await requestFileUploadUrl({
    original_filename: 'report.pdf',
    content_type: 'application/pdf',
    checksum_sha256: 'abc',
  })
  await completeFileUpload('file id', { checksum_sha256: 'abc' })
  await fetchFileDownloadUrl('file id')
  await deleteFileStorageAsset('file id')

  assert.deepEqual(calls.map(({ method, path }) => ({ method, path })), [
    { method: 'POST', path: '/files/upload-url/' },
    { method: 'POST', path: '/files/file%20id/complete/' },
    { method: 'GET', path: '/files/file%20id/download-url/' },
    { method: 'DELETE', path: '/files/file%20id/' },
  ])
  assert.ok(calls.every((call) => call.authorization === 'Bearer file-token'))
})

test('presigned upload sends only storage headers and redacts query credentials from traces', async () => {
  const traces: HttpTraceEvent[] = []
  let seenInit: RequestInit | undefined
  configureApiClient({
    tokenReader: () => 'must-not-leak',
    traceSink: (event) => traces.push(event),
  })
  globalThis.fetch = async (_url, init) => {
    seenInit = init
    return new Response(null, { status: 200 })
  }

  await putPresignedFile(
    'https://storage.example.test/bucket/file?X-Amz-Signature=secret',
    new Blob(['file']),
    { contentType: 'text/plain', timeoutMs: 1_000 },
  )

  const headers = new Headers(seenInit?.headers)
  assert.equal(headers.get('Content-Type'), 'text/plain')
  assert.equal(headers.has('Authorization'), false)
  assert.equal(headers.has('X-Request-ID'), false)
  assert.equal(traces[0].url, 'https://storage.example.test/bucket/file')
  assert.equal(traces[0].url.includes('secret'), false)
})

test('presigned upload converts its timeout into ApiError without retrying', async () => {
  let attempts = 0
  globalThis.fetch = async (_url, init) => {
    attempts += 1
    return await new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => {
        reject(new DOMException('aborted', 'AbortError'))
      }, { once: true })
    })
  }

  await assert.rejects(
    () => putPresignedFile(
      'https://storage.example.test/bucket/file',
      new Blob(['file']),
      { contentType: 'text/plain', timeoutMs: 5 },
    ),
    (error) => {
      assert.ok(error instanceof ApiError)
      assert.equal(error.errorCode, 'ETIMEDOUT')
      assert.equal(error.retryable, false)
      return true
    },
  )
  assert.equal(attempts, 1)
})

/** Build the backend's shared success envelope for file client fixtures. */
function envelope(data: unknown) {
  return {
    code: 200,
    message: 'ok',
    data,
    timestamp: '2026-07-10T00:00:00Z',
  }
}
