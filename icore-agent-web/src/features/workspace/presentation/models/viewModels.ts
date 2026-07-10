export interface WorkspaceAttachment {
  file_uuid: string
  original_filename?: string
  filename?: string
  content_type?: string
  download_url?: string
  mode?: string
  [key: string]: any
}

export interface SessionListItem {
  sessionId: string
  title: string
  subtitle?: string
  snippet?: string
  updatedAt: number
  messageCount?: number
  rank?: number
}

export interface ProjectSummary {
  id: string
  title: string
  sessions: number
  assets: number
  updatedAt: number
}

export interface ScenarioShortcut {
  id: string
  label: string
  emoji: string
  description?: string
  agentHint?: string
  panel?: string
  pillClass?: string
}

export interface ScenarioTemplate {
  id: string
  title: string
  description?: string
  agentHint?: string
  outputs?: string[]
  phases?: string[]
  sections?: string[]
}

export interface ComposerMode {
  id: string
  label: string
  emoji: string
  panel?: string
  pillClass?: string
}

export interface PendingImage {
  id: string
  file: File
  url: string
}

export interface PendingDataFile {
  id: string
  file: File
}

export interface ComposerSubmitPayload {
  message: string
  imageFiles: File[]
  dataFiles: File[]
}

export interface SearchBarExpose {
  focus(): void
  clearPendingImage(id?: string): void
  clearPendingDataFiles(): void
}
