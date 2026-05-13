import { getBrowserStorage, readStoredString, writeStoredString } from './browserStorage.js'

export const WORKSPACE_ONBOARDING_KEY = 'icore_onboarding_completed'
export const WORKSPACE_RECENT_SESSIONS_KEY = 'icore_recent_sessions'

/**
 * Read whether the onboarding modal has already been completed.
 * @param {Storage | null | undefined} [storage]
 */
export function getWorkspaceOnboardingComplete(storage = getBrowserStorage()) {
  return readStoredString(storage, WORKSPACE_ONBOARDING_KEY, '') === 'true'
}

/**
 * Persist the onboarding completion flag.
 * @param {Storage | null | undefined} [storage]
 * @param {boolean} completed
 */
export function setWorkspaceOnboardingComplete(storage = getBrowserStorage(), completed = true) {
  writeStoredString(storage, WORKSPACE_ONBOARDING_KEY, completed ? 'true' : 'false')
}

/**
 * Read the recent session list from browser storage.
 * @param {Storage | null | undefined} [storage]
 */
export function getRecentSessions(storage = getBrowserStorage()) {
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
 * @param {Storage | null | undefined} [storage]
 * @param {Array<any>} sessions
 */
export function setRecentSessions(storage = getBrowserStorage(), sessions = []) {
  writeStoredString(storage, WORKSPACE_RECENT_SESSIONS_KEY, JSON.stringify(sessions))
}
