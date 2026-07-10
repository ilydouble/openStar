import type {
  ChatStreamOptions,
  PageOptions,
  TranscriptionOptions,
} from '../domain/models/workspace'
import type { WorkspaceGateway } from '../domain/repositories/workspaceGateway'
import type { WorkspacePreferencesRepository } from '../domain/repositories/workspacePreferencesRepository'

/** Bind workspace transport and preference ports for presentation consumers. */
export function createWorkspaceApplication(
  gateway: WorkspaceGateway,
  preferences: WorkspacePreferencesRepository,
) {
  return {
    streamTurn: (
      message: string,
      sessionId: string,
      agentHint = '',
      options: ChatStreamOptions = {},
    ) => gateway.chatEventStream(message, sessionId, agentHint, options),
    streamLegacyTurn: (
      message: string,
      sessionId: string,
      agentHint = '',
      options: ChatStreamOptions = {},
    ) => gateway.chatStream(message, sessionId, agentHint, options),
    chat: (message: string, sessionId: string, agentHint = '') =>
      gateway.chat(message, sessionId, agentHint),
    runSequential: (task: string, useDocker = false) =>
      gateway.runSequential(task, useDocker),
    finalizeSession: (sessionId: string) => gateway.finalizeSession(sessionId),
    deleteSession: (sessionId: string) => gateway.clearSession(sessionId),
    loadSession: (sessionId: string) => gateway.getSessionState(sessionId),
    loadSessions: () => gateway.fetchAllSessions(),
    searchSessions: (query: string, options: PageOptions = {}) =>
      gateway.searchSessions(query, options),
    createSessionId: () => gateway.newSessionId(),
    uploadFile: (file: File) => gateway.uploadFileAsset(file),
    getFileDownloadUrl: (fileUuid: string) => gateway.getFileDownloadUrl(fileUuid),
    deleteFile: (fileUuid: string) => gateway.deleteFileAsset(fileUuid),
    transcribeSpeech: (audioBlob: Blob, options: TranscriptionOptions = {}) =>
      gateway.transcribeSpeech(audioBlob, options),
    isOnboardingComplete: () => preferences.isOnboardingComplete(),
    completeOnboarding: () => preferences.setOnboardingComplete(true),
    getRecentSessions: () => preferences.getRecentSessions(),
    setRecentSessions: (sessions: Parameters<WorkspacePreferencesRepository['setRecentSessions']>[0]) =>
      preferences.setRecentSessions(sessions),
  }
}
