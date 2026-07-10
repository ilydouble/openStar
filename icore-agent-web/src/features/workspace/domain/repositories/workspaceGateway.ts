import type {
  ChatStreamOptions,
  PageOptions,
  SessionPage,
  SessionSearchResult,
  TranscriptionOptions,
  WorkspaceRecord,
} from '../models/workspace'

export interface WorkspaceGateway {
  chatEventStream(
    message: string,
    sessionId: string,
    agentHint?: string,
    options?: ChatStreamOptions,
  ): AsyncGenerator<WorkspaceRecord>
  chatStream(
    message: string,
    sessionId: string,
    agentHint?: string,
    options?: ChatStreamOptions,
  ): AsyncGenerator<WorkspaceRecord>
  chat(message: string, sessionId: string, agentHint?: string): Promise<unknown>
  runSequential(task: string, useDocker?: boolean): Promise<unknown>
  finalizeSession(sessionId: string): Promise<unknown>
  clearSession(sessionId: string): Promise<unknown>
  getSessionState(sessionId: string): Promise<WorkspaceRecord>
  fetchSessions(options?: PageOptions): Promise<SessionPage>
  fetchAllSessions(): Promise<{ sessions: WorkspaceRecord[]; total: number }>
  searchSessions(query: string, options?: PageOptions): Promise<SessionSearchResult>
  newSessionId(): string
  uploadFileAsset(file: File): Promise<WorkspaceRecord>
  getFileDownloadUrl(fileUuid: string): Promise<WorkspaceRecord>
  deleteFileAsset(fileUuid: string): Promise<unknown>
  transcribeSpeech(audioBlob: Blob, options?: TranscriptionOptions): Promise<string>
}
