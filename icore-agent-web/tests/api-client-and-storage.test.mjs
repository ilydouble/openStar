import test from 'node:test'
import assert from 'node:assert/strict'

import { createJsonClient, formatApiErrorMessage, readJsonResponse } from '../src/shared/api/client'
import i18n from '../src/shared/i18n'
import { fetchAllSessions, searchSessions } from '../src/api/agent.js'
import {
  WORKSPACE_ONBOARDING_KEY,
  WORKSPACE_RECENT_SESSIONS_KEY,
  getWorkspaceOnboardingComplete,
  getRecentSessions,
  setWorkspaceOnboardingComplete,
  setRecentSessions,
} from '../src/stores/workspace'

test('json client adds auth headers and preserves structured error detail', async () => {
  const seen = []
  global.fetch = async (url, options) => {
    seen.push({ url, options })
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const client = createJsonClient({
    getAccessToken: () => 'token-1',
  })
  const payload = await client.post('/api/test', { hello: 'world' })

  assert.deepEqual(payload, { ok: true })
  assert.equal(seen[0].options.headers.Authorization, 'Bearer token-1')
  assert.equal(seen[0].options.headers['Content-Type'], 'application/json')

  await assert.rejects(
    () =>
      readJsonResponse(
        new Response(JSON.stringify({ detail: 'broken' }), {
          status: 422,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    (err) => {
      assert.equal(err.message, 'broken')
      assert.equal(err.status, 422)
      assert.ok(!/^HTTP /.test(err.message))
      return true
    },
  )
})

test('formatApiErrorMessage localizes common HTTP statuses without prefix', () => {
  i18n.global.locale.value = 'en-US'
  assert.equal(
    formatApiErrorMessage(401, 'Unauthorized', '/api/v1/agent/chat'),
    'Please sign in to continue.',
  )
  assert.equal(
    formatApiErrorMessage(404, 'missing', '/api/v1/account/send-verification-code'),
    'This email is not registered. Please sign up for a trial account first.',
  )
  assert.equal(
    formatApiErrorMessage(404, 'missing', '/api/v1/agent/sessions/x'),
    'The requested item was not found.',
  )
  assert.ok(!/^HTTP /.test(formatApiErrorMessage(500, 'boom', '/api/test')))
})

test('readJsonResponse surfaces localized 401 errors', async () => {
  i18n.global.locale.value = 'en-US'
  await assert.rejects(
    () =>
      readJsonResponse(
        new Response(JSON.stringify({ detail: 'Unauthorized' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
          url: 'http://localhost/api/v1/agent/chat',
        }),
      ),
    (err) => {
      assert.equal(err.message, 'Please sign in to continue.')
      assert.equal(err.status, 401)
      assert.ok(!/^HTTP /.test(err.message))
      return true
    },
  )
})

test('workspace store persists onboarding flag and recent sessions', () => {
  const backing = new Map()
  const storage = {
    getItem(key) {
      return backing.has(key) ? backing.get(key) : null
    },
    setItem(key, value) {
      backing.set(key, value)
    },
    removeItem(key) {
      backing.delete(key)
    },
  }

  assert.equal(getWorkspaceOnboardingComplete(storage), false)
  setWorkspaceOnboardingComplete(storage, true)
  assert.equal(storage.getItem(WORKSPACE_ONBOARDING_KEY), 'true')
  assert.equal(getWorkspaceOnboardingComplete(storage), true)

  setRecentSessions(storage, [{ sessionId: 's1' }])
  assert.deepEqual(getRecentSessions(storage), [{ sessionId: 's1' }])
  assert.equal(storage.getItem(WORKSPACE_RECENT_SESSIONS_KEY), JSON.stringify([{ sessionId: 's1' }]))
})

test('fetchAllSessions loads every page ordered by updated_at desc', async () => {
  const calls = []
  global.fetch = async (url) => {
    calls.push(String(url))
    if (url.includes('offset=0')) {
      return new Response(
        JSON.stringify({
          code: 200,
          message: '操作成功',
          data: {
            sessions: [
              { public_id: 's1', title: 'First', updated_at: 2, message_count: 3 },
              { public_id: 's2', title: 'Second', updated_at: 1, message_count: 1 },
            ],
            total: 3,
            limit: 100,
            offset: 0,
          },
          timestamp: '2026-05-21T00:00:00+00:00',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }
    return new Response(
      JSON.stringify({
        code: 200,
        message: '操作成功',
        data: {
          sessions: [{ public_id: 's3', title: 'Third', updated_at: 0, message_count: 5 }],
          total: 3,
          limit: 100,
          offset: 2,
        },
        timestamp: '2026-05-21T00:00:00+00:00',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    )
  }

  const { sessions, total } = await fetchAllSessions()

  assert.equal(total, 3)
  assert.equal(sessions.length, 3)
  assert.equal(calls.length, 2)
  assert.ok(calls[0].includes('/api/v1/agent/sessions?limit=100&offset=0'))
  assert.ok(calls[1].includes('offset=2'))
})

test('searchSessions calls the full-text search endpoint', async () => {
  const calls = []
  global.fetch = async (url) => {
    calls.push(String(url))
    return new Response(
      JSON.stringify({
        code: 200,
        message: '操作成功',
        data: {
          query: 'budget',
          sessions: [
            {
              public_id: 's1',
              title: 'Weekly Review',
              updated_at: 10,
              rank: 0.42,
              snippet: 'Review the <mark>budget</mark> forecast',
            },
          ],
          total: 1,
          limit: 20,
          offset: 0,
        },
        timestamp: '2026-05-21T00:00:00+00:00',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    )
  }

  const payload = await searchSessions('budget')

  assert.equal(payload.total, 1)
  assert.equal(payload.sessions[0].snippet.includes('<mark>budget</mark>'), true)
  assert.ok(calls[0].includes('/api/v1/agent/sessions/search?q=budget&limit=20&offset=0'))
})

test('searchSessions returns empty payload for blank query', async () => {
  global.fetch = async () => {
    throw new Error('fetch should not run for blank query')
  }

  const payload = await searchSessions('   ')
  assert.deepEqual(payload, {
    query: '',
    sessions: [],
    total: 0,
    limit: 20,
    offset: 0,
  })
})
