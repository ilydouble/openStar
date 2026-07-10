import assert from 'node:assert/strict'
import { afterEach, test } from 'vitest'

import { AxiosHeaders, type AxiosAdapter } from 'axios'

import { configureApiClient, createApiClient } from '../../../shared/api/api-client'
import { fetchMe, updateMemoryFact } from './accountApi'

afterEach(() => {
  configureApiClient({ tokenReader: () => '' })
})

test('account API delegates reads and writes to the shared client', async () => {
  const calls: Array<{ method: string; path: string; body: unknown }> = []
  const adapter: AxiosAdapter = async (config) => {
    calls.push({
      method: String(config.method || '').toUpperCase(),
      path: String(config.url || ''),
      body: parseBody(config.data),
    })
    return response(config, config.url === '/account/me'
      ? { id: 'user-1', email: 'user@example.test' }
      : { id: 'fact-1', value: 'updated' })
  }
  configureApiClient({
    tokenReader: () => 'account-token',
    client: createApiClient({ adapter, tokenReader: () => 'account-token' }),
  })

  assert.deepEqual(await fetchMe(), { id: 'user-1', email: 'user@example.test' })
  assert.deepEqual(await updateMemoryFact('fact-1', 'updated'), {
    id: 'fact-1',
    value: 'updated',
  })
  assert.deepEqual(calls, [
    { method: 'GET', path: '/account/me', body: undefined },
    {
      method: 'PUT',
      path: '/account/memory/facts/fact-1',
      body: { value: 'updated' },
    },
  ])
})

/** Build one successful account API response. */
function response(config: Parameters<AxiosAdapter>[0], data: unknown) {
  return {
    config,
    status: 200,
    statusText: 'OK',
    data: {
      code: 200,
      message: 'ok',
      data,
      timestamp: '2026-07-10T00:00:00Z',
    },
    headers: new AxiosHeaders(),
  }
}

/** Decode Axios-transformed JSON request data for assertions. */
function parseBody(value: unknown): unknown {
  return typeof value === 'string' ? JSON.parse(value) : value
}
