import test, { afterEach } from 'node:test'
import assert from 'node:assert/strict'

import { AxiosHeaders } from 'axios'

import {
  configureApiClient,
  createApiClient,
  formatApiErrorMessage,
} from '../src/shared/api/api-client'
import i18n from '../src/shared/i18n'
import { fetchAllSessions, searchSessions } from '../src/features/workspace/infrastructure/agentApi'
import {
  WORKSPACE_ONBOARDING_KEY,
  WORKSPACE_RECENT_SESSIONS_KEY,
  getWorkspaceOnboardingComplete,
  getRecentSessions,
  setWorkspaceOnboardingComplete,
  setRecentSessions,
} from '../src/features/workspace/application/workspaceStore'

afterEach(() => {
  configureApiClient({ tokenReader: () => '' })
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
  installApiAdapter(async (config) => {
    calls.push({ path: config.url, params: config.params })
    const offset = Number(config.params?.offset || 0)
    return envelope({
      sessions: offset === 0
        ? [
            { public_id: 's1', title: 'First', updated_at: 2, message_count: 3 },
            { public_id: 's2', title: 'Second', updated_at: 1, message_count: 1 },
          ]
        : [{ public_id: 's3', title: 'Third', updated_at: 0, message_count: 5 }],
      total: 3,
      limit: 100,
      offset,
    })
  })

  const { sessions, total } = await fetchAllSessions()

  assert.equal(total, 3)
  assert.equal(sessions.length, 3)
  assert.equal(calls.length, 2)
  assert.equal(calls[0].path, '/agent/sessions')
  assert.deepEqual(calls[0].params, { limit: 100, offset: 0 })
  assert.equal(calls[1].params.offset, 2)
})

test('searchSessions calls the full-text search endpoint', async () => {
  const calls = []
  installApiAdapter(async (config) => {
    calls.push({ path: config.url, params: config.params })
    return envelope({
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
    })
  })

  const payload = await searchSessions('budget')

  assert.equal(payload.total, 1)
  assert.equal(payload.sessions[0].snippet.includes('<mark>budget</mark>'), true)
  assert.equal(calls[0].path, '/agent/sessions/search')
  assert.deepEqual(calls[0].params, { q: 'budget', limit: 20, offset: 0 })
})

test('searchSessions returns empty payload for blank query', async () => {
  installApiAdapter(async () => {
    throw new Error('fetch should not run for blank query')
  })

  const payload = await searchSessions('   ')
  assert.deepEqual(payload, {
    query: '',
    sessions: [],
    total: 0,
    limit: 20,
    offset: 0,
  })
})

/** Install an isolated Axios adapter behind the shared client facade. */
function installApiAdapter(handler) {
  const adapter = async (config) => ({
    config,
    status: 200,
    statusText: 'OK',
    data: await handler(config),
    headers: new AxiosHeaders(),
  })
  configureApiClient({
    tokenReader: () => '',
    client: createApiClient({ adapter, baseURL: '/api/v1', retryDelayMs: 0 }),
  })
}

/** Build the backend's shared success envelope for adapter fixtures. */
function envelope(data) {
  return {
    code: 200,
    message: '操作成功',
    data,
    timestamp: '2026-05-21T00:00:00+00:00',
  }
}
