import assert from 'node:assert/strict'
import { afterEach, test } from 'vitest'

import { ApiError, configureApiClient, type HttpTraceEvent } from './api-client'
import { openSseResponse } from './sse-client'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
  configureApiClient({ tokenReader: () => '' })
})

test('SSE client applies auth and trace headers without buffering the response', async () => {
  const traces: HttpTraceEvent[] = []
  let seenUrl = ''
  let seenInit: RequestInit | undefined
  configureApiClient({
    tokenReader: () => 'sse-token',
    traceSink: (event) => traces.push(event),
  })
  globalThis.fetch = async (url, init) => {
    seenUrl = String(url)
    seenInit = init
    return new Response('data: {"type":"done"}\n\n', {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Request-ID': 'server-sse-id',
      },
    })
  }

  const response = await openSseResponse('/agent/chat', {
    method: 'POST',
    body: { message: 'hello' },
  })

  const headers = new Headers(seenInit?.headers)
  assert.equal(seenUrl, '/api/v1/agent/chat')
  assert.equal(headers.get('Authorization'), 'Bearer sse-token')
  assert.ok(headers.get('X-Request-ID'))
  assert.equal(headers.get('Accept'), 'text/event-stream')
  assert.equal(await response.text(), 'data: {"type":"done"}\n\n')
  assert.deepEqual(traces.map((event) => event.phase), ['request', 'success'])
  assert.equal(traces[1].requestId, 'server-sse-id')
})

test('SSE client does not retry failed POST streams', async () => {
  let attempts = 0
  globalThis.fetch = async () => {
    attempts += 1
    return new Response(JSON.stringify({
      code: 503,
      message: 'service unavailable',
      data: null,
      timestamp: '2026-07-10T00:00:00Z',
      error_code: 'service_unavailable',
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  await assert.rejects(
    () => openSseResponse('/agent/chat', { method: 'POST', body: { message: 'hello' } }),
    (error) => {
      assert.ok(error instanceof ApiError)
      assert.equal(error.status, 503)
      return true
    },
  )
  assert.equal(attempts, 1)
})

test('SSE client preserves AbortError cancellation semantics', async () => {
  globalThis.fetch = async () => {
    throw new DOMException('aborted', 'AbortError')
  }

  await assert.rejects(
    () => openSseResponse('/agent/chat'),
    (error) => error instanceof Error && error.name === 'AbortError',
  )
})
