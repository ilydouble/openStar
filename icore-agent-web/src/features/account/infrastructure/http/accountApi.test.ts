import assert from 'node:assert/strict'
import { afterEach, test } from 'vitest'

import { AxiosHeaders, type AxiosAdapter } from 'axios'

import { configureApiClient, createApiClient } from '../../../../shared/infrastructure/http'
import { HttpAccountRepository } from './accountApi'

afterEach(() => {
  configureApiClient({ tokenReader: () => '' })
})

test('account repository maps profile and memory DTOs at the HTTP boundary', async () => {
  const calls: Array<{ method: string; path: string; body: unknown }> = []
  const adapter: AxiosAdapter = async (config) => {
    calls.push({
      method: String(config.method || '').toUpperCase(),
      path: String(config.url || ''),
      body: parseBody(config.data),
    })
    return response(
      config,
      config.url === '/account/me' ? profileDto() : memoryFactDto(),
    )
  }
  configureApiClient({
    tokenReader: () => 'account-token',
    client: createApiClient({ adapter, tokenReader: () => 'account-token' }),
  })
  const repository = new HttpAccountRepository()

  const profile = await repository.getProfile()
  const fact = await repository.updateMemoryFact(1, 'updated')

  assert.equal(profile.organizationName, 'Test Org')
  assert.equal(profile.planLabel, 'Trial')
  assert.equal(fact.lastConfirmedAt, 10)
  assert.deepEqual(calls, [
    { method: 'GET', path: '/account/me', body: undefined },
    {
      method: 'PUT',
      path: '/account/memory/facts/1',
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

/** Build a complete account profile transport fixture. */
function profileDto() {
  return {
    id: 'user-1',
    name: 'Test User',
    email: 'user@example.test',
    plan: 'trial',
    plan_label: 'Trial',
    organization_id: 'org-1',
    organization_name: 'Test Org',
    roles: ['owner'],
    byok: { enabled: false, api_key: '', api_base: '', model: '' },
    usage: {},
    created_at: 1,
    updated_at: 2,
  }
}

/** Build one durable-memory transport fixture. */
function memoryFactDto() {
  return {
    id: 1,
    category: 'preference',
    key: 'response_style',
    value: 'updated',
    confidence: 1,
    salience: 0.8,
    source: 'explicit',
    last_confirmed_at: 10,
    updated_at: 10,
  }
}

/** Decode Axios-transformed JSON request data for assertions. */
function parseBody(value: unknown): unknown {
  return typeof value === 'string' ? JSON.parse(value) : value
}
