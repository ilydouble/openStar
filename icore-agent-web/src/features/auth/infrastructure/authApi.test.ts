import assert from 'node:assert/strict'
import { afterEach, test } from 'vitest'

import { AxiosHeaders, type AxiosAdapter } from 'axios'

import { configureApiClient, createApiClient } from '../../../shared/api/api-client'
import { clearSession, getAccessToken } from '../application/session'
import { emailLogin } from './authApi'

afterEach(() => {
  clearSession()
  configureApiClient({ tokenReader: () => '' })
})

test('email login uses the shared client and persists the unwrapped session token', async () => {
  let seenPath = ''
  let seenBody: unknown
  const adapter: AxiosAdapter = async (config) => {
    seenPath = String(config.url || '')
    seenBody = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    return {
      config,
      status: 200,
      statusText: 'OK',
      data: {
        code: 200,
        message: 'ok',
        data: {
          access_token: 'login-token',
          user: { id: 'user-1', email: 'user@example.test' },
        },
        timestamp: '2026-07-10T00:00:00Z',
      },
      headers: new AxiosHeaders(),
    }
  }
  configureApiClient({
    tokenReader: getAccessToken,
    client: createApiClient({ adapter, tokenReader: getAccessToken }),
  })

  await emailLogin({ email: 'user@example.test', verification_code: '123456' })

  assert.equal(seenPath, '/account/login')
  assert.deepEqual(seenBody, {
    email: 'user@example.test',
    verification_code: '123456',
  })
  assert.equal(getAccessToken(), 'login-token')
})
