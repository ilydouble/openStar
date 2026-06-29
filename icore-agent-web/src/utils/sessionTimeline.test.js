import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  applyTurnEvent,
  hydrateSessionTimeline,
  isVisibleTimelineItem,
  timelineToChatRows,
  upsertTimelineItem,
} from './sessionTimeline.js'

test('hydrateSessionTimeline reads canonical turns and attachments', () => {
  const timeline = hydrateSessionTimeline({
    session_id: 'session-1',
    attachments: [{ file_uuid: 'file-1', original_filename: 'report.pdf', mode: 'data' }],
    turns: [{
      turn_id: 'turn-1',
      status: 'completed',
      model: 'glm-4',
      provider: 'zai',
      usage: { total_tokens: 42 },
      items: [{
        item_id: 'item-1',
        type: 'agent_message',
        status: 'completed',
        payload: { id: 'item-1', type: 'agent_message', status: 'completed', text: 'Done' },
      }],
    }],
  })

  assert.equal(timeline.sessionId, 'session-1')
  assert.equal(timeline.turns.length, 1)
  assert.equal(timeline.turns[0].turnId, 'turn-1')
  assert.equal(timeline.turns[0].items[0].payload.text, 'Done')
  assert.equal(timeline.attachments[0].file_uuid, 'file-1')
})

test('upsertTimelineItem updates existing items by stable item id', () => {
  const turn = { turnId: 'turn-1', status: 'in_progress', items: [] }

  upsertTimelineItem(turn, {
    item_id: 'assistant-1',
    type: 'agent_message',
    status: 'in_progress',
    payload: { id: 'assistant-1', type: 'agent_message', text: 'Hel' },
  })
  upsertTimelineItem(turn, {
    item_id: 'assistant-1',
    type: 'agent_message',
    status: 'completed',
    payload: { id: 'assistant-1', type: 'agent_message', text: 'Hello' },
  })

  assert.equal(turn.items.length, 1)
  assert.equal(turn.items[0].status, 'completed')
  assert.equal(turn.items[0].payload.text, 'Hello')
})

test('applyTurnEvent builds turns, appends deltas, and preserves failed items', () => {
  const timeline = hydrateSessionTimeline({ session_id: 'session-1', turns: [], attachments: [] })

  applyTurnEvent(timeline, { type: 'turn_started', session_id: 'session-1', turn_id: 'turn-1' })
  applyTurnEvent(timeline, {
    type: 'item_started',
    session_id: 'session-1',
    turn_id: 'turn-1',
    item_id: 'assistant-1',
    item: { id: 'assistant-1', type: 'agent_message', status: 'in_progress', text: '' },
  })
  applyTurnEvent(timeline, {
    type: 'item_delta',
    session_id: 'session-1',
    turn_id: 'turn-1',
    item_id: 'assistant-1',
    delta: { text_append: 'Hel' },
  })
  applyTurnEvent(timeline, {
    type: 'item_delta',
    session_id: 'session-1',
    turn_id: 'turn-1',
    item_id: 'assistant-1',
    delta: { text_append: 'lo' },
  })
  applyTurnEvent(timeline, {
    type: 'turn_failed',
    session_id: 'session-1',
    turn_id: 'turn-1',
    error: { message: 'model unavailable' },
  })

  assert.equal(timeline.turns[0].status, 'failed')
  assert.equal(timeline.turns[0].error.message, 'model unavailable')
  assert.equal(timeline.turns[0].items[0].payload.text, 'Hello')
})

test('applyTurnEvent replaces terminal turns and appends tool-call arguments', () => {
  const timeline = hydrateSessionTimeline({ session_id: 'session-1', turns: [], attachments: [] })

  applyTurnEvent(timeline, { type: 'turn_started', session_id: 'session-1', turn_id: 'turn-1' })
  applyTurnEvent(timeline, {
    type: 'item_started',
    session_id: 'session-1',
    turn_id: 'turn-1',
    item_id: 'tool-1',
    item: {
      id: 'tool-1',
      type: 'tool_call',
      status: 'streaming',
      function: { name: 'number_comparator', arguments_text: '' },
    },
  })
  applyTurnEvent(timeline, {
    type: 'item_delta',
    session_id: 'session-1',
    turn_id: 'turn-1',
    item_id: 'tool-1',
    item_type: 'tool_call',
    delta: {
      arguments_append: '{"left":',
      name: 'number_comparator',
      provider_tool_call_id: 'provider-tool-1',
      index: 0,
    },
  })
  applyTurnEvent(timeline, {
    type: 'item_delta',
    session_id: 'session-1',
    turn_id: 'turn-1',
    item_id: 'tool-1',
    item_type: 'tool_call',
    delta: { arguments_append: '2,"right":1}' },
  })
  assert.equal(
    timeline.turns[0].items[0].payload.function.arguments_text,
    '{"left":2,"right":1}',
  )
  applyTurnEvent(timeline, {
    type: 'turn_completed',
    session_id: 'session-1',
    turn_id: 'turn-1',
    turn: {
      turn_id: 'turn-1',
      status: 'completed',
      model: 'test-model',
      provider: 'test-provider',
      usage: { total_tokens: 3 },
      items: [{
        id: 'assistant-1',
        type: 'agent_message',
        status: 'completed',
        text: 'Done',
      }],
    },
  })

  assert.equal(timeline.turns[0].status, 'completed')
  assert.equal(timeline.turns[0].model, 'test-model')
  assert.equal(timeline.turns[0].items.length, 1)
  assert.equal(timeline.turns[0].items[0].payload.text, 'Done')
})

test('timelineToChatRows renders user attachments and hides context items by default', () => {
  const timeline = hydrateSessionTimeline({
    session_id: 'session-1',
    attachments: [
      {
        file_uuid: 'img-1',
        original_filename: 'photo.png',
        filename: 'photo.png',
        content_type: 'image/png',
        mode: 'image',
        download_url: 'https://example.com/photo.png',
      },
      {
        file_uuid: 'doc-1',
        original_filename: 'report.pdf',
        filename: 'report.pdf',
        content_type: 'application/pdf',
        mode: 'data',
      },
    ],
    turns: [{
      turn_id: 'turn-1',
      status: 'completed',
      items: [
        {
          item_id: 'context-1',
          type: 'context',
          status: 'completed',
          payload: { id: 'context-1', type: 'context', kind: 'session_summary', content: 'hidden' },
        },
        {
          item_id: 'user-1',
          type: 'user_message',
          status: 'completed',
          payload: {
            id: 'user-1',
            type: 'user_message',
            content: [{ type: 'text', text: 'Analyze these' }],
            metadata: { file_uuids: ['img-1', 'doc-1'], display_caption: 'Analyze these' },
          },
        },
      ],
    }],
  })

  const rows = timelineToChatRows(timeline)

  assert.equal(rows.length, 1)
  assert.equal(rows[0].type, 'composite')
  assert.equal(rows[0].images.length, 1)
  assert.equal(rows[0].dataAttachments.length, 1)
  assert.equal(rows[0].caption, 'Analyze these')
})

test('isVisibleTimelineItem hides empty assistant text placeholders', () => {
  assert.equal(isVisibleTimelineItem({
    type: 'agent_message',
    status: 'in_progress',
    payload: { text: '' },
  }), false)
  assert.equal(isVisibleTimelineItem({
    type: 'agent_message',
    status: 'completed',
    payload: { text: '  ' },
  }), false)
  assert.equal(isVisibleTimelineItem({
    type: 'agent_message',
    status: 'in_progress',
    payload: { text: 'Hel' },
  }), true)
})
