import {
  buildAttachmentLookup,
  buildMessageAttachmentPayloads,
  collectMessageAttachmentUuids,
  resolveAttachmentCaption,
} from './sessionMessageHydration'
import { resolveUserMessageDisplayContent } from '../../application/services/scenarioPrompt'
import type {
  SessionTimeline,
  TimelineItem,
  TimelineTurn,
} from '../../domain/models/timeline'

type AnyRecord = Record<string, any>

export type { SessionTimeline, TimelineItem, TimelineTurn }

interface TimelineRow extends AnyRecord {
  id: string
  turnId: string
  itemId: string
  role: string
  content: string
}

interface TimelineToRowsOptions {
  attachments?: AnyRecord[]
  showContextItems?: boolean
  templateLabels?: Record<string, string>
}

/** Normalize one backend session item wrapper or raw turn event item. */
export function normalizeTimelineItem(input: AnyRecord = {}): TimelineItem {
  const payload = input?.payload && typeof input.payload === 'object'
    ? { ...input.payload }
    : { ...(input || {}) }
  const itemId = String(input?.item_id || input?.id || payload.id || '').trim()
  if (itemId && !payload.id) payload.id = itemId
  const type = String(input?.type || payload.type || '').trim()
  const status = String(input?.status || payload.status || '').trim()
  return {
    itemId,
    type,
    status,
    payload,
  }
}

/** Normalize one backend turn payload into the frontend canonical timeline shape. */
export function normalizeTimelineTurn(input: AnyRecord = {}): TimelineTurn {
  return {
    turnId: String(input?.turn_id || input?.turnId || '').trim(),
    status: String(input?.status || 'in_progress'),
    model: input?.model ?? null,
    provider: input?.provider ?? null,
    usage: input?.usage ?? null,
    error: input?.error ?? null,
    startedAt: input?.started_at || input?.startedAt || null,
    completedAt: input?.completed_at || input?.completedAt || null,
    durationMs: input?.duration_ms ?? input?.durationMs ?? null,
    items: (Array.isArray(input?.items) ? input.items : [])
      .map((item: AnyRecord) => normalizeTimelineItem(item))
      .filter((item: TimelineItem) => item.itemId),
  }
}

/** Hydrate the canonical session timeline returned by the backend session state API. */
export function hydrateSessionTimeline(state: AnyRecord = {}): SessionTimeline {
  return {
    sessionId: String(state.session_id || state.sessionId || '').trim(),
    summary: state.summary || null,
    turns: (Array.isArray(state.turns) ? state.turns : [])
      .map((turn: AnyRecord) => normalizeTimelineTurn(turn))
      .filter((turn: TimelineTurn) => turn.turnId),
    attachments: Array.isArray(state.attachments) ? [...state.attachments] : [],
  }
}

/** Return whether a timeline item should be rendered in the normal chat view. */
export function isVisibleTimelineItem(item: TimelineItem | null | undefined, options: { showContext?: boolean } = {}): boolean {
  if (!item || typeof item !== 'object') return false
  if (item.type === 'context') return Boolean(options.showContext)
  if (item.type === 'agent_message') {
    return Boolean(String(item.payload?.text || '').trim())
  }
  return true
}

/** Insert or replace one item in a turn by stable item id. */
export function upsertTimelineItem(turn: TimelineTurn, itemInput: AnyRecord): TimelineItem | null {
  if (!turn || !Array.isArray(turn.items)) return null
  const item = normalizeTimelineItem(itemInput)
  if (!item.itemId) return null
  const index = turn.items.findIndex((existing: TimelineItem) => existing.itemId === item.itemId)
  if (index >= 0) {
    turn.items.splice(index, 1, item)
  } else {
    turn.items.push(item)
  }
  return item
}

/** Apply one raw typed turn event to the canonical timeline in place. */
export function applyTurnEvent(timeline: SessionTimeline, event: AnyRecord): SessionTimeline {
  if (!timeline || !event || typeof event !== 'object') return timeline
  const type = String(event.type || '').trim()
  const turnId = String(event.turn_id || event.turnId || '').trim()
  if (!turnId) return timeline

  const turn = ensureTimelineTurn(timeline, turnId)
  if (type === 'turn_started') {
    turn.status = 'in_progress'
    return timeline
  }
  if (type === 'item_started' || type === 'item_completed') {
    upsertTimelineItem(turn, {
      item_id: event.item_id,
      type: event.item?.type,
      status: event.item?.status,
      payload: event.item || {},
    })
    return timeline
  }
  if (type === 'item_delta') {
    appendTimelineItemDelta(turn, event)
    return timeline
  }
  if (type === 'turn_completed') {
    replaceTurnIfProvided(timeline, turnId, event.turn)
    const completed = ensureTimelineTurn(timeline, turnId)
    completed.status = 'completed'
    completed.error = null
    return timeline
  }
  if (type === 'turn_failed') {
    replaceTurnIfProvided(timeline, turnId, event.turn)
    const failed = ensureTimelineTurn(timeline, turnId)
    failed.status = 'failed'
    failed.error = event.error || failed.error || { message: 'Agent turn failed' }
    return timeline
  }
  if (type === 'turn_aborted') {
    replaceTurnIfProvided(timeline, turnId, event.turn)
    const aborted = ensureTimelineTurn(timeline, turnId)
    aborted.status = 'aborted'
    return timeline
  }
  return timeline
}

/** Convert canonical timeline items into the legacy chat-row shape during UI migration. */
export function timelineToChatRows(timeline: SessionTimeline, options: TimelineToRowsOptions = {}): TimelineRow[] {
  const attachments = Array.isArray(options.attachments)
    ? options.attachments
    : timeline?.attachments || []
  const lookup = buildAttachmentLookup(attachments)
  const assignedUuids = new Set<string>()
  const showContextItems = Boolean(options.showContextItems)
  const templateLabels = options.templateLabels || {}
  const rows: TimelineRow[] = []

  for (const turn of timeline?.turns || []) {
    const toolSteps = turn.items
      .filter((item) => item.type === 'tool_call')
      .map((item, index) => toolCallStep(item, index))

    for (const item of turn.items) {
      if (item.type === 'context' && !showContextItems) continue
      if (item.type === 'user_message') {
        rows.push(userMessageRow(turn, item, lookup, assignedUuids, templateLabels))
      } else if (item.type === 'agent_message') {
        rows.push(agentMessageRow(turn, item, toolSteps))
      } else if (showContextItems && item.type === 'context') {
        rows.push(contextDebugRow(turn, item))
      }
    }
  }

  return rows.filter(Boolean)
}

/** Return the text content of a user message timeline item. */
export function userMessageText(payload: AnyRecord): string {
  const blocks = Array.isArray(payload?.content) ? payload.content : []
  return blocks
    .map((block) => String(block?.text || '').trim())
    .filter(Boolean)
    .join('\n')
}

/** Find one turn by public turn id. */
function findTimelineTurn(timeline: SessionTimeline, turnId: string): TimelineTurn | undefined {
  return timeline.turns.find((turn: TimelineTurn) => turn.turnId === turnId)
}

/** Return an existing turn or append a new in-progress turn. */
function ensureTimelineTurn(timeline: SessionTimeline, turnId: string): TimelineTurn {
  if (!Array.isArray(timeline.turns)) timeline.turns = []
  const existing = findTimelineTurn(timeline, turnId)
  if (existing) return existing
  const turn = {
    turnId,
    status: 'in_progress',
    error: null,
    model: null,
    provider: null,
    usage: null,
    startedAt: null,
    completedAt: null,
    durationMs: null,
    items: [],
  }
  timeline.turns.push(turn)
  return turn
}

/** Replace a turn with a complete backend turn payload when the event provides one. */
function replaceTurnIfProvided(timeline: SessionTimeline, turnId: string, rawTurn: AnyRecord | null | undefined): void {
  if (!rawTurn || typeof rawTurn !== 'object') return
  const next = normalizeTimelineTurn(rawTurn)
  if (!next.turnId) next.turnId = turnId
  const index = timeline.turns.findIndex((turn) => turn.turnId === turnId)
  if (index >= 0) timeline.turns.splice(index, 1, next)
  else timeline.turns.push(next)
}

/** Append a streamed delta to the matching timeline item payload. */
function appendTimelineItemDelta(turn: TimelineTurn, event: AnyRecord): void {
  const itemId = String(event.item_id || '').trim()
  if (!itemId) return
  let item = turn.items.find((existing: TimelineItem) => existing.itemId === itemId)
  const eventItemType = String(event.item_type || '').trim()
  if (!item) {
    if (eventItemType === 'tool_call') {
      item = {
        itemId,
        type: 'tool_call',
        status: 'streaming',
        payload: {
          id: itemId,
          type: 'tool_call',
          status: 'streaming',
          provider_tool_call_id: event.delta?.provider_tool_call_id || null,
          index: event.delta?.index ?? null,
          function: {
            name: event.delta?.name || null,
            arguments_text: '',
            arguments_json: null,
          },
        },
      }
    } else {
      item = {
        itemId,
        type: 'agent_message',
        status: 'in_progress',
        payload: { id: itemId, type: 'agent_message', status: 'in_progress', text: '' },
      }
    }
    turn.items.push(item)
  }
  if (item.type === 'tool_call' || eventItemType === 'tool_call') {
    const append = String(event.delta?.arguments_append || '')
    const fn = item.payload?.function && typeof item.payload.function === 'object'
      ? item.payload.function
      : {}
    item.payload = {
      ...item.payload,
      provider_tool_call_id:
        event.delta?.provider_tool_call_id ?? item.payload?.provider_tool_call_id ?? null,
      index: event.delta?.index ?? item.payload?.index ?? null,
      function: {
        ...fn,
        name: event.delta?.name ?? fn.name ?? null,
        arguments_text: String(fn.arguments_text || '') + append,
      },
    }
    return
  }
  const text = String(event.delta?.text_append ?? event.delta?.text ?? '')
  if (text) {
    item.payload = {
      ...item.payload,
      text: String(item.payload?.text || '') + text,
    }
  } else {
    item.payload = {
      ...item.payload,
      delta: { ...(item.payload?.delta || {}), ...(event.delta || {}) },
    }
  }
}

/** Project one user message item to the temporary chat-row shape. */
function userMessageRow(
  turn: TimelineTurn,
  item: TimelineItem,
  lookup: Map<string, AnyRecord>,
  assignedUuids: Set<string>,
  templateLabels: Record<string, string>,
): TimelineRow {
  const payload = item.payload || {}
  const metadata = payload.metadata && typeof payload.metadata === 'object'
    ? payload.metadata
    : {}
  const content = userMessageText(payload)
  const displayContent = resolveUserMessageDisplayContent(
    { content, metadata },
    templateLabels,
  )
  const base = {
    id: `${turn.turnId}-${item.itemId}`,
    turnId: turn.turnId,
    itemId: item.itemId,
    role: 'user',
    content: displayContent,
    steps: [],
    stepsCollapsed: true,
    streaming: item.status === 'in_progress',
  }

  const rawUuids = Array.isArray(metadata.file_uuids) ? metadata.file_uuids : []
  const fileUuids = collectMessageAttachmentUuids(rawUuids, assignedUuids)
  if (!fileUuids.length) return base

  const { images, dataAttachments } = buildMessageAttachmentPayloads(fileUuids, lookup)
  if (!images.length && !dataAttachments.length) return base

  const hasImages = images.length > 0
  const hasData = dataAttachments.length > 0
  const caption = resolveAttachmentCaption({ content, metadata })
  let rowType = 'data'
  if (hasImages && hasData) rowType = 'composite'
  else if (hasImages) rowType = 'image'

  return {
    ...base,
    type: rowType,
    content: '',
    ...(hasImages ? { images } : {}),
    ...(hasData ? { dataAttachments } : {}),
    ...(caption ? { caption } : {}),
  }
}

/** Project one assistant item to the temporary chat-row shape. */
function agentMessageRow(turn: TimelineTurn, item: TimelineItem, toolSteps: AnyRecord[]): TimelineRow {
  const text = String(item.payload?.text || '')
  return {
    id: `${turn.turnId}-${item.itemId}`,
    turnId: turn.turnId,
    itemId: item.itemId,
    role: 'assistant',
    content: text,
    steps: toolSteps,
    stepsCollapsed: turn.status !== 'in_progress',
    streaming: item.status === 'in_progress' || turn.status === 'in_progress',
  }
}

/** Project one context item to an optional debug chat-row shape. */
function contextDebugRow(turn: TimelineTurn, item: TimelineItem): TimelineRow {
  return {
    id: `${turn.turnId}-${item.itemId}`,
    turnId: turn.turnId,
    itemId: item.itemId,
    role: 'context',
    content: String(item.payload?.content || ''),
    contextKind: String(item.payload?.kind || 'context'),
  }
}

/** Project one tool call item to the legacy assistant step summary shape. */
function toolCallStep(item: TimelineItem, index: number): AnyRecord {
  const fn = item.payload?.function || {}
  const argsJson = fn.arguments_json
  let inputPreview = String(fn.arguments_text || '').trim()
  if (!inputPreview && argsJson && typeof argsJson === 'object') {
    try {
      inputPreview = JSON.stringify(argsJson)
    } catch {
      inputPreview = ''
    }
  }
  return {
    step: Number(item.payload?.index ?? index + 1),
    tool: String(fn.name || ''),
    input_preview: inputPreview,
    status: item.status,
  }
}
