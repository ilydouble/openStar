import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import { chatEventStream, chatStream, createCommerceDiagnosis } from './agent.js'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
})

test('chatStream converts turn item deltas into token events', async () => {
  mockChatStreamResponse([
    sse({ type: 'turn_started', session_id: 'session-1', turn_id: 'turn-1' }),
    sse({
      type: 'item_started',
      session_id: 'session-1',
      turn_id: 'turn-1',
      item_id: 'assistant-1',
      item: { type: 'agent_message', id: 'assistant-1', text: '' },
    }),
    sse({
      type: 'item_delta',
      session_id: 'session-1',
      turn_id: 'turn-1',
      item_id: 'assistant-1',
      delta: { text_append: 'Hel' },
    }),
    sse({
      type: 'item_delta',
      session_id: 'session-1',
      turn_id: 'turn-1',
      item_id: 'assistant-1',
      delta: { text_append: 'lo' },
    }),
    sse({
      type: 'item_completed',
      session_id: 'session-1',
      turn_id: 'turn-1',
      item_id: 'assistant-1',
      item: { type: 'agent_message', id: 'assistant-1', text: 'Hello' },
    }),
    sse({
      type: 'turn_completed',
      session_id: 'session-1',
      turn_id: 'turn-1',
      reply: 'Hello',
    }),
    'data: [DONE]\n\n',
  ])

  const events = await collect(chatStream('Hi', 'session-1'))

  assert.equal(events.map((event) => event.text).join(''), 'Hello')
})

test('chatEventStream yields backend typed events without projection', async () => {
  mockChatStreamResponse([
    sse({ type: 'turn_started', session_id: 'session-1', turn_id: 'turn-1' }),
    sse({
      type: 'item_delta',
      session_id: 'session-1',
      turn_id: 'turn-1',
      item_id: 'assistant-1',
      delta: { text_append: 'Hel' },
    }),
    sse({
      type: 'turn_aborted',
      session_id: 'session-1',
      turn_id: 'turn-1',
      reply: '',
    }),
    'data: [DONE]\n\n',
  ])

  const events = await collect(chatEventStream('Hi', 'session-1'))

  assert.deepEqual(events.map((event) => event.type), [
    'turn_started',
    'item_delta',
    'turn_aborted',
  ])
  assert.equal(events[1].item_id, 'assistant-1')
  assert.equal(events[1].delta.text_append, 'Hel')
})

test('chatStream falls back to completed assistant item text when no deltas arrive', async () => {
  mockChatStreamResponse([
    sse({
      type: 'item_completed',
      session_id: 'session-1',
      turn_id: 'turn-1',
      item_id: 'assistant-1',
      item: { type: 'agent_message', id: 'assistant-1', text: 'Fallback reply' },
    }),
    sse({
      type: 'turn_completed',
      session_id: 'session-1',
      turn_id: 'turn-1',
      reply: 'Fallback reply',
    }),
    'data: [DONE]\n\n',
  ])

  const events = await collect(chatStream('Hi', 'session-1'))

  assert.equal(events.map((event) => event.text).join(''), 'Fallback reply')
})

test('chatStream reports turn_failed error messages', async () => {
  mockChatStreamResponse([
    sse({
      type: 'turn_failed',
      session_id: 'session-1',
      turn_id: 'turn-1',
      error: { message: 'model unavailable', code: 'RuntimeError' },
    }),
    'data: [DONE]\n\n',
  ])

  await assert.rejects(
    async () => collect(chatStream('Hi', 'session-1')),
    /model unavailable/,
  )
})

test('createCommerceDiagnosis posts uploaded CSV file uuid to commerce API', async () => {
  let request = null
  globalThis.fetch = async (url, init) => {
    request = { url, init }
    return jsonResponse({
      code: 200,
      message: 'OK',
      data: {
        diagnosis_id: 'diagnosis-1',
        agent_profile: 'commerce_diagnosis_v1',
        source_file: { file_uuid: 'file-1', filename: 'orders.csv', row_count: 3 },
        metrics: { sku_count: 3 },
        risks: [],
        tasks: [],
        report_summary: 'done',
      },
      timestamp: '2026-01-01T00:00:00Z',
    })
  }

  const report = await createCommerceDiagnosis('file-1', { locale: 'zh-CN' })

  assert.equal(request.url, '/api/v1/commerce/diagnoses')
  assert.equal(request.init.method, 'POST')
  assert.equal(request.init.headers['Content-Type'], 'application/json')
  assert.deepEqual(JSON.parse(request.init.body), {
    file_uuid: 'file-1',
    locale: 'zh-CN',
  })
  assert.equal(report.agent_profile, 'commerce_diagnosis_v1')
  assert.equal(report.source_file.filename, 'orders.csv')
})

function mockChatStreamResponse(frames) {
  globalThis.fetch = async () => ({
    ok: true,
    body: streamFromFrames(frames),
    headers: { get: () => 'text/event-stream' },
    url: '/api/v1/agent/chat',
  })
}

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    url: '/api/v1/commerce/diagnoses',
    headers: { get: () => 'application/json' },
    json: async () => payload,
  }
}

function streamFromFrames(frames) {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame))
      }
      controller.close()
    },
  })
}

function sse(payload) {
  return `data: ${JSON.stringify(payload)}\n\n`
}

async function collect(generator) {
  const events = []
  for await (const event of generator) {
    events.push(event)
  }
  return events
}
