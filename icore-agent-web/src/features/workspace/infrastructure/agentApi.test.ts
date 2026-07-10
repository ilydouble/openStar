// @ts-nocheck
import assert from 'node:assert/strict'
import { afterEach, test } from 'vitest'

import { AxiosHeaders } from 'axios'

import { configureApiClient, createApiClient } from '../../../shared/infrastructure/http'
import { QuotaExceededError, chatEventStream, chatStream, transcribeSpeech } from './agentApi'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
  configureApiClient({ tokenReader: () => '' })
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

test('chatEventStream preserves quota errors from the shared SSE client', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({
    code: 402,
    message: 'quota exceeded',
    data: { current_plan: 'trial', upgrade_url: '/account' },
    timestamp: '2026-07-10T00:00:00Z',
    error_code: 'quota_exceeded',
  }), {
    status: 402,
    headers: { 'Content-Type': 'application/json' },
  })

  await assert.rejects(
    async () => collect(chatEventStream('Hi', 'session-1')),
    (error) => {
      assert.ok(error instanceof QuotaExceededError)
      assert.equal(error.currentPlan, 'trial')
      assert.equal(error.upgradeUrl, '/account')
      return true
    },
  )
})

test('transcribeSpeech uses shared FormData transport with the long request timeout', async () => {
  let seenConfig
  const adapter = async (config) => {
    seenConfig = config
    return {
      config,
      status: 200,
      statusText: 'OK',
      data: {
        code: 200,
        message: 'ok',
        data: { text: 'Transcribed text' },
        timestamp: '2026-07-10T00:00:00Z',
      },
      headers: new AxiosHeaders(),
    }
  }
  configureApiClient({
    tokenReader: () => 'voice-token',
    client: createApiClient({ adapter, tokenReader: () => 'voice-token' }),
  })
  const signal = new AbortController().signal

  const text = await transcribeSpeech(new Blob(['audio'], { type: 'audio/webm' }), {
    language: 'zh-CN',
    filename: 'voice.webm',
    signal,
  })

  assert.equal(text, 'Transcribed text')
  assert.equal(seenConfig.url, '/agent/transcribe')
  assert.equal(seenConfig.timeout, 120_000)
  assert.equal(seenConfig.signal, signal)
  assert.ok(seenConfig.data instanceof FormData)
  assert.equal(seenConfig.data.get('language'), 'zh-CN')
  assert.equal(AxiosHeaders.from(seenConfig.headers).get('Authorization'), 'Bearer voice-token')
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
