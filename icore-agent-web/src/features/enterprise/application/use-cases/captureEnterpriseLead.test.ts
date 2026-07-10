import assert from 'node:assert/strict'
import { afterEach, test } from 'vitest'

import { AxiosHeaders, type AxiosAdapter } from 'axios'

import { configureApiClient, createApiClient } from '../../../../shared/infrastructure/http'
import { HttpLeadRepository } from '../../infrastructure/http/leadApi'
import { captureEnterpriseLead } from './captureEnterpriseLead'

afterEach(() => {
  configureApiClient({ tokenReader: () => '' })
})

test('enterprise lead capture normalizes domain input and maps the HTTP contract', async () => {
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
          lead: {
            id: 'lead-1',
            name: 'Ada Lovelace',
            email: 'ada@example.test',
            company: 'Analytical Engines',
            team_size: '11-50',
            use_case: 'Automate research',
            needs_byok: true,
            needs_private_deploy: false,
            source: 'enterprise-page',
            intent: 'enterprise',
            created_at: 1_784_000_000,
          },
        },
        timestamp: '2026-07-10T00:00:00Z',
      },
      headers: new AxiosHeaders(),
    }
  }
  configureApiClient({
    tokenReader: () => '',
    client: createApiClient({ adapter, tokenReader: () => '' }),
  })

  const lead = await captureEnterpriseLead(new HttpLeadRepository(), {
    name: '  Ada Lovelace  ',
    email: '  ADA@EXAMPLE.TEST  ',
    company: '  Analytical Engines  ',
    teamSize: '11-50',
    useCase: '  Automate research  ',
    needsByok: true,
    needsPrivateDeploy: false,
    source: 'enterprise-page',
    intent: 'enterprise',
  })

  assert.equal(seenPath, '/account/leads')
  assert.deepEqual(seenBody, {
    name: 'Ada Lovelace',
    email: 'ada@example.test',
    company: 'Analytical Engines',
    team_size: '11-50',
    use_case: 'Automate research',
    needs_byok: true,
    needs_private_deploy: false,
    source: 'enterprise-page',
    intent: 'enterprise',
  })
  assert.deepEqual(lead, {
    id: 'lead-1',
    name: 'Ada Lovelace',
    email: 'ada@example.test',
    company: 'Analytical Engines',
    teamSize: '11-50',
    useCase: 'Automate research',
    needsByok: true,
    needsPrivateDeploy: false,
    source: 'enterprise-page',
    intent: 'enterprise',
    createdAt: 1_784_000_000,
  })
})
