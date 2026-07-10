import assert from 'node:assert/strict'
import { test, vi } from 'vitest'

import type { WorkspaceGateway } from '../domain/repositories/workspaceGateway'
import type { WorkspacePreferencesRepository } from '../domain/repositories/workspacePreferencesRepository'
import { createWorkspaceApplication } from './createWorkspaceApplication'

test('workspace application delegates session and onboarding workflows through ports', async () => {
  const fetchAllSessions = vi.fn(async () => ({ sessions: [{ public_id: 's1' }], total: 1 }))
  const setOnboardingComplete = vi.fn()
  const application = createWorkspaceApplication(
    { fetchAllSessions } as unknown as WorkspaceGateway,
    {
      isOnboardingComplete: () => false,
      setOnboardingComplete,
      getRecentSessions: () => [],
      setRecentSessions: () => undefined,
    } satisfies WorkspacePreferencesRepository,
  )

  assert.deepEqual(await application.loadSessions(), {
    sessions: [{ public_id: 's1' }],
    total: 1,
  })
  assert.equal(application.isOnboardingComplete(), false)
  application.completeOnboarding()
  assert.deepEqual(setOnboardingComplete.mock.calls, [[true]])
})
