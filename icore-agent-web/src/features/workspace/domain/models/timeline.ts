import type { WorkspaceRecord } from './workspace'

export type TimelineItemType =
  | 'context'
  | 'user_message'
  | 'agent_message'
  | 'reasoning'
  | 'plan'
  | 'tool_call'

export type TimelineItemStatus =
  | 'in_progress'
  | 'streaming'
  | 'ready'
  | 'running'
  | 'completed'
  | 'failed'
  | 'declined'

export interface TimelinePayloadBase<TType extends TimelineItemType> {
  id?: string
  type?: TType
  status?: TimelineItemStatus
  created_at?: string | null
  completed_at?: string | null
}

export interface ContextItemPayload extends TimelinePayloadBase<'context'> {
  kind: string
  role_hint?: 'user'
  content: string
}

export interface UserInputBlock {
  type: 'text' | 'image'
  text?: string | null
  image_file_uuid?: string | null
  image_url?: string | null
}

export interface UserMessageItemPayload extends TimelinePayloadBase<'user_message'> {
  content: UserInputBlock[]
  metadata: WorkspaceRecord
}

export interface TextItemPayload<TType extends 'agent_message' | 'reasoning' | 'plan'>
  extends TimelinePayloadBase<TType> {
  text: string
}

export interface ToolFunctionPayload {
  name: string | null
  arguments_text: string
  arguments_json: WorkspaceRecord | null
}

export interface ToolCallResultPayload {
  content: string | null
  structured_content: WorkspaceRecord | null
}

export interface ToolCallErrorPayload {
  message: string
  code: string | null
}

export interface ToolCallItemPayload extends TimelinePayloadBase<'tool_call'> {
  provider?: string | null
  provider_tool_call_id?: string | null
  index?: number | null
  tool_type?: 'function' | 'mcp'
  function: ToolFunctionPayload
  result?: ToolCallResultPayload | null
  error?: ToolCallErrorPayload | null
  started_at?: string | null
  duration_ms?: number | null
}

interface TimelineItemBase<TType extends TimelineItemType, TPayload> {
  itemId: string
  type: TType
  status: TimelineItemStatus
  payload: TPayload
}

export type ContextTimelineItem = TimelineItemBase<'context', ContextItemPayload>
export type UserMessageTimelineItem = TimelineItemBase<'user_message', UserMessageItemPayload>
export type AgentMessageTimelineItem = TimelineItemBase<
  'agent_message',
  TextItemPayload<'agent_message'>
>
export type ReasoningTimelineItem = TimelineItemBase<'reasoning', TextItemPayload<'reasoning'>>
export type PlanTimelineItem = TimelineItemBase<'plan', TextItemPayload<'plan'>>
export type ToolCallTimelineItem = TimelineItemBase<'tool_call', ToolCallItemPayload>

export type TimelineItem =
  | ContextTimelineItem
  | UserMessageTimelineItem
  | AgentMessageTimelineItem
  | ReasoningTimelineItem
  | PlanTimelineItem
  | ToolCallTimelineItem

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
