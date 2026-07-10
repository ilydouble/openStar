import assert from 'node:assert/strict'
import { afterEach, test } from 'vitest'

import { AxiosHeaders, type AxiosAdapter } from 'axios'

import { configureApiClient, createApiClient } from '../../../../shared/infrastructure/http'
import type { AuthSession, AuthUser } from '../../domain/models/authSession'
import type { SessionRepository } from '../../domain/repositories/sessionRepository'
import { HttpAuthRepository } from '../../infrastructure/http/authApi'
import { loginWithEmail } from './authenticate'

afterEach(() => {
  configureApiClient({ tokenReader: () => '' })
})

test('email login maps the transport DTO and persists the domain session', async () => {
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
        data: sessionDto(),
        timestamp: '2026-07-10T00:00:00Z',
      },
      headers: new AxiosHeaders(),
    }
  }
  configureApiClient({
    tokenReader: () => '',
    client: createApiClient({ adapter, tokenReader: () => '' }),
  })
  const sessionRepository = new InMemorySessionRepository()

  const session = await loginWithEmail(
    new HttpAuthRepository(),
    sessionRepository,
    { email: 'user@example.test', verificationCode: '123456' },
  )

  assert.equal(seenPath, '/account/login')
  assert.deepEqual(seenBody, {
    email: 'user@example.test',
    verification_code: '123456',
  })
  assert.equal(session.accessToken, 'login-token')
  assert.equal(session.user?.planLabel, 'Trial')
  assert.equal(sessionRepository.getAccessToken(), 'login-token')
})

/** In-memory session port used to assert application orchestration. */
class InMemorySessionRepository implements SessionRepository {
  private session: AuthSession | null = null

  /** Return the current token or an empty string. */
  getAccessToken(): string {
    return this.session?.accessToken || ''
  }

  /** Return the current user when a session is present. */
  getUser(): AuthUser | null {
    return this.session?.user || null
  }

  /** Store the most recently authenticated session. */
  save(session: AuthSession): void {
    this.session = session
  }

  /** Clear the in-memory session. */
  clear(): void {
    this.session = null
  }
}

/** Build a complete backend authentication fixture. */
function sessionDto() {
  return {
    access_token: 'login-token',
    token_type: 'bearer',
    user: {
      id: 'user-1',
      name: 'Test User',
      email: 'user@example.test',
      plan: 'trial',
      plan_label: 'Trial',
      organization_id: 'org-1',
      organization_name: 'Test Org',
      roles: ['owner'],
      byok: {},
      usage: {},
      created_at: 1,
      updated_at: 2,
    },
  }
}
