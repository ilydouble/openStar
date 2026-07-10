import type { RecentSession } from '../models/workspace'

export interface WorkspacePreferencesRepository {
  isOnboardingComplete(): boolean
  setOnboardingComplete(completed?: boolean): void
  getRecentSessions(): RecentSession[]
  setRecentSessions(sessions: RecentSession[]): void
}
