import assert from 'node:assert/strict'
import { test, vi } from 'vitest'

import type { AccountPlan, AccountProfile, AccountTeam } from '../../domain/models/account'
import type { AccountRepository } from '../../domain/repositories/accountRepository'
import { loadAccountOverview } from './accountOperations'

test('account overview loads admin data only for administrators', async () => {
  const getAdminOverview = vi.fn(async () => ({ marker: 'admin' }))
  const repository = {
    getProfile: async () => profileFixture(['admin']),
    getPlan: async () => planFixture(),
    getTeam: async () => teamFixture(),
    getAdminOverview,
  } as unknown as AccountRepository

  const overview = await loadAccountOverview(repository)

  assert.equal(overview.profile.email, 'user@example.test')
  assert.equal(overview.team?.organization.name, 'Test Org')
  assert.deepEqual(overview.adminOverview, { marker: 'admin' })
  assert.equal(getAdminOverview.mock.calls.length, 1)
})

/** Build a typed account profile fixture. */
function profileFixture(roles: string[]): AccountProfile {
  return {
    id: 'user-1',
    name: 'Test User',
    email: 'user@example.test',
    plan: 'trial',
    planLabel: 'Trial',
    organizationId: 'org-1',
    organizationName: 'Test Org',
    roles,
    byok: { enabled: false, apiKey: '', apiBase: '', model: '' },
    usage: {},
    createdAt: 1,
    updatedAt: 2,
  }
}

/** Build a typed plan fixture. */
function planFixture(): AccountPlan {
  return {
    plan: 'trial',
    label: 'Trial',
    limits: { tasks: 10, attachments: 5 },
    usage: {
      tasks: 1,
      tokens: 2,
      attachments: 0,
      estimatedCost: 0,
      modelCalls: 1,
      activeModels: 1,
    },
    modelsUsed: ['test-model'],
    byModel: {},
    quotaPeriod: { start: 1, nextReset: 2 },
    byok: { enabled: false, apiKey: '', apiBase: '', model: '' },
  }
}

/** Build a typed team fixture. */
function teamFixture(): AccountTeam {
  return {
    organization: { id: 'org-1', name: 'Test Org', knowledgeScope: 'organization' },
    members: [],
    currentUserId: 'user-1',
  }
}
