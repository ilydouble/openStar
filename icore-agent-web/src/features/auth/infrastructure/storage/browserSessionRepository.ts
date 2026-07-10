import {
  getBrowserStorage,
  readStoredString,
  removeStoredKey,
  writeStoredString,
} from '../../../../shared/infrastructure/storage'
import type { AuthSession, AuthUser } from '../../domain/models/authSession'
import type { SessionRepository } from '../../domain/repositories/sessionRepository'
import { authTrace, isAuthTracingEnabled } from '../observability/authTrace'

export const AUTH_TOKEN_STORAGE_KEY = 'icore_access_token'
export const AUTH_USER_STORAGE_KEY = 'icore_current_user'

export type StorageProvider = () => Storage | null

/** Browser-backed authentication session repository with a same-tab token fallback. */
export class BrowserSessionRepository implements SessionRepository {
  private volatileAccessToken = ''

  constructor(private readonly storageProvider: StorageProvider = getBrowserStorage) {}

  /** Read the current access token from persistent or same-tab storage. */
  getAccessToken(): string {
    const persisted = readStoredString(this.storageProvider(), AUTH_TOKEN_STORAGE_KEY, '')
    if (persisted) this.volatileAccessToken = persisted
    return persisted || this.volatileAccessToken
  }

  /** Read the currently persisted user profile when it has a valid object shape. */
  getUser(): AuthUser | null {
    const raw = readStoredString(this.storageProvider(), AUTH_USER_STORAGE_KEY, '')
    if (!raw) return null
    try {
      const value: unknown = JSON.parse(raw)
      return isAuthUser(value) ? value : null
    } catch {
      return null
    }
  }

  /** Persist an authenticated session without ever writing token values to logs. */
  save(session: AuthSession): void {
    const storage = this.storageProvider()
    this.volatileAccessToken = session.accessToken
    writeStoredString(storage, AUTH_TOKEN_STORAGE_KEY, session.accessToken)
    if (session.user) {
      writeStoredString(storage, AUTH_USER_STORAGE_KEY, JSON.stringify(session.user))
    } else {
      removeStoredKey(storage, AUTH_USER_STORAGE_KEY)
    }
    this.tracePersistence(storage, session)
  }

  /** Clear all authentication state for the current browser profile. */
  clear(): void {
    this.volatileAccessToken = ''
    const storage = this.storageProvider()
    removeStoredKey(storage, AUTH_TOKEN_STORAGE_KEY)
    removeStoredKey(storage, AUTH_USER_STORAGE_KEY)
  }

  /** Emit token-presence diagnostics when explicit auth tracing is enabled. */
  private tracePersistence(storage: Storage | null, session: AuthSession): void {
    if (!isAuthTracingEnabled()) return
    const persisted = readStoredString(storage, AUTH_TOKEN_STORAGE_KEY, '')
    authTrace('session persisted', {
      storageWritable: Boolean(storage),
      tokenPresent: Boolean(persisted || this.volatileAccessToken),
      tokenLength: persisted.length || this.volatileAccessToken.length,
      tokenMatches: persisted === session.accessToken,
      hasUser: Boolean(session.user),
    })
  }
}

/** Narrow persisted JSON to the minimum stable authentication user shape. */
function isAuthUser(value: unknown): value is AuthUser {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const candidate = value as Partial<AuthUser>
  return typeof candidate.id === 'string' && typeof candidate.email === 'string'
}
