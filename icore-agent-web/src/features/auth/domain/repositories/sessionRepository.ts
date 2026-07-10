import type { AuthSession, AuthUser } from '../models/authSession'

export interface SessionRepository {
  getAccessToken(): string
  getUser(): AuthUser | null
  save(session: AuthSession): void
  clear(): void
}
