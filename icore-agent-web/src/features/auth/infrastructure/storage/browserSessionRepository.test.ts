import assert from 'node:assert/strict'
import { test } from 'vitest'

import type { AuthSession } from '../../domain/models/authSession'
import {
  AUTH_TOKEN_STORAGE_KEY,
  BrowserSessionRepository,
} from './browserSessionRepository'

test('browser session repository persists and clears authentication state', () => {
  const storage = createMemoryStorage()
  const repository = new BrowserSessionRepository(() => storage)

  repository.save(sessionFixture())

  assert.equal(repository.getAccessToken(), 'token-1')
  assert.equal(repository.getUser()?.email, 'user@example.test')
  assert.equal(storage.getItem(AUTH_TOKEN_STORAGE_KEY), 'token-1')

  repository.clear()
  assert.equal(repository.getAccessToken(), '')
  assert.equal(repository.getUser(), null)
})

/** Build an isolated in-memory implementation of the browser Storage contract. */
function createMemoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear() {
      values.clear()
    },
    getItem(key: string) {
      return values.get(key) ?? null
    },
    key(index: number) {
      return [...values.keys()][index] ?? null
    },
    removeItem(key: string) {
      values.delete(key)
    },
    setItem(key: string, value: string) {
      values.set(key, value)
    },
  }
}

/** Build a complete domain session fixture. */
function sessionFixture(): AuthSession {
  return {
    accessToken: 'token-1',
    tokenType: 'bearer',
    user: {
      id: 'user-1',
      name: 'Test User',
      email: 'user@example.test',
      plan: 'trial',
      planLabel: 'Trial',
      organizationId: 'org-1',
      organizationName: 'Test Org',
      roles: ['owner'],
      byok: {},
      usage: {},
      createdAt: 1,
      updatedAt: 2,
    },
  }
}
