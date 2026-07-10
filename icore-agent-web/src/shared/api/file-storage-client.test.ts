import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import { ApiError, configureApiClient, type HttpTraceEvent } from './api-client'
import { putPresignedFile } from './file-storage-client'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
  configureApiClient({ tokenReader: () => '' })
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
