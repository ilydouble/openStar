import {
  getBrowserStorage,
  readStoredString,
  writeStoredString,
} from '../../../shared/infrastructure/storage'

export const WORKSPACE_ONBOARDING_KEY = 'icore_onboarding_completed'
export const WORKSPACE_RECENT_SESSIONS_KEY = 'icore_recent_sessions'

export interface RecentSession {
  sessionId?: string
  [key: string]: unknown
}

/**
 * Read whether the onboarding modal has already been completed.
 */
export function getWorkspaceOnboardingComplete(
  storage: Storage | null | undefined = getBrowserStorage(),
): boolean {
  return readStoredString(storage, WORKSPACE_ONBOARDING_KEY, '') === 'true'
}

/**
 * Persist the onboarding completion flag.
 */
export function setWorkspaceOnboardingComplete(
  storage: Storage | null | undefined = getBrowserStorage(),
  completed = true,
): void {
  writeStoredString(storage, WORKSPACE_ONBOARDING_KEY, completed ? 'true' : 'false')
}

/**
 * Read the recent session list from browser storage.
 */
export function getRecentSessions(
  storage: Storage | null | undefined = getBrowserStorage(),
): RecentSession[] {
  const raw = readStoredString(storage, WORKSPACE_RECENT_SESSIONS_KEY, '[]')
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

/**
 * Persist the recent session list for workspace restoration.
 */
export function setRecentSessions(
  storage: Storage | null | undefined = getBrowserStorage(),
  sessions: RecentSession[] = [],
): void {
  writeStoredString(storage, WORKSPACE_RECENT_SESSIONS_KEY, JSON.stringify(sessions))
}
