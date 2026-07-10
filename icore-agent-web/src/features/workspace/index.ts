export { workspaceApplication } from './composition'
export { QuotaExceededError } from './domain/errors/quotaExceededError'
export type {
  ChatStreamOptions,
  SessionSearchResult,
  WorkspaceRecord,
} from './domain/models/workspace'

/** Load the primary workspace page through the feature route boundary. */
export function loadWorkspacePage() {
  return import('./presentation/pages/HomePage.vue')
}
