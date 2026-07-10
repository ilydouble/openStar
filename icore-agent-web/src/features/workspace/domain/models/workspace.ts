export type WorkspaceRecord = Record<string, any>

export interface ChatStreamOptions {
  signal?: AbortSignal
  fileUuids?: string[]
  displayCaption?: string
  agentMessage?: string
  templateId?: string
  incognito?: boolean
}

export interface PageOptions {
  limit?: number
  offset?: number
}

export interface SessionSearchResult {
  query: string
  sessions: WorkspaceRecord[]
  total: number
  limit: number
  offset: number
}

export interface SessionPage {
  sessions: WorkspaceRecord[]
  total: number
  limit?: number
  offset?: number
}

export interface TranscriptionOptions {
  language?: string
  signal?: AbortSignal
  filename?: string
}

export interface QuotaExceededData {
  current_plan?: string
  upgrade_url?: string
}

export interface RecentSession {
  sessionId?: string
  [key: string]: unknown
}
