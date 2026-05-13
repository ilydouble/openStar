import test from 'node:test'
import assert from 'node:assert/strict'

import { createJsonClient, readJsonResponse } from '../src/api/client.js'
import {
  WORKSPACE_ONBOARDING_KEY,
  WORKSPACE_RECENT_SESSIONS_KEY,
  getWorkspaceOnboardingComplete,
  getRecentSessions,
  setWorkspaceOnboardingComplete,
  setRecentSessions,
} from '../src/stores/workspace.js'

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
    /broken/,
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
