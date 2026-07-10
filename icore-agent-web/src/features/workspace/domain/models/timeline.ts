import type { WorkspaceRecord } from './workspace'

export interface TimelineItem {
  itemId: string
  type: string
  status: string
  payload: WorkspaceRecord
}

export interface TimelineTurn {
  turnId: string
  status: string
  model: unknown
  provider: unknown
  usage: unknown
  error: unknown
  startedAt: unknown
  completedAt: unknown
  durationMs: unknown
  items: TimelineItem[]
}

export interface SessionTimeline {
  sessionId: string
  summary: unknown
  turns: TimelineTurn[]
  attachments: WorkspaceRecord[]
}
