import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import { chatEventStream, chatStream } from './agent.js'

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

function mockChatStreamResponse(frames) {
  globalThis.fetch = async () => ({
    ok: true,
    body: streamFromFrames(frames),
    headers: { get: () => 'text/event-stream' },
    url: '/api/v1/agent/chat',
  })
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
