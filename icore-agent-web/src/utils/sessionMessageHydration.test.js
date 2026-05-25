import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  composeScenarioPrompt,
  hasScenarioPromptEnvelope,
  resolveTemplateBubbleText,
  resolveUserMessageDisplayContent,
  stripScenarioPromptEnvelope,
} from './scenarioPrompt.js'
import {
  collectMessageAttachmentUuids,
  hydrateSessionMessages,
} from './sessionMessageHydration.js'

test('composeScenarioPrompt keeps instructions out of the visible bubble text', () => {
  const template = {
    sections: ['Executive summary', 'Action plan'],
    outputs: ['Executive summary', 'Action plan'],
  }
  const agentMessage = composeScenarioPrompt('Analyze this market', template)
  assert.equal(hasScenarioPromptEnvelope(agentMessage), true)
  assert.equal(
    stripScenarioPromptEnvelope(agentMessage),
    'Analyze this market',
  )
  assert.equal(
    resolveTemplateBubbleText('Creative Brief', 'Analyze this market'),
    'Creative Brief',
  )
})

test('resolveUserMessageDisplayContent prefers template label from metadata', () => {
  const composed = [
    'Evaluate the competitive landscape',
    '',
    '---',
    'Please answer in markdown using this exact section order when it fits the task:',
    '## Executive summary',
  ].join('\n')

  assert.equal(
    resolveUserMessageDisplayContent(
      {
        content: composed,
        metadata: { template_id: 'research' },
      },
      { research: 'Market Research' },
    ),
    'Market Research',
  )
})

test('collectMessageAttachmentUuids assigns each file only once', () => {
  const assigned = new Set()
  assert.deepEqual(
    collectMessageAttachmentUuids(['a', 'b', 'a'], assigned),
    ['a', 'b'],
  )
  assert.deepEqual(
    collectMessageAttachmentUuids(['a', 'c'], assigned),
    ['c'],
  )
})

test('hydrateSessionMessages shows attachments only on their first message', () => {
  const attachments = [
    {
      file_uuid: 'img-1',
      original_filename: 'photo.png',
      filename: 'photo.png',
      content_type: 'image/png',
      mode: 'image',
      download_url: 'https://example.com/img-1',
    },
    {
      file_uuid: 'doc-1',
      original_filename: 'report.pdf',
      filename: 'report.pdf',
      content_type: 'application/pdf',
      mode: 'data',
    },
  ]

  const messages = hydrateSessionMessages({
    sessionId: 'session-1',
    attachments,
    messages: [
      {
        role: 'user',
        content: 'Analyze these',
        metadata: {
          file_uuids: ['img-1', 'doc-1'],
          display_caption: 'Analyze these',
        },
      },
      { role: 'assistant', content: 'Done' },
      {
        role: 'user',
        content: 'Follow up question',
        metadata: { file_uuids: ['img-1', 'doc-1'] },
      },
    ],
  })

  assert.equal(messages[0].type, 'composite')
  assert.equal(messages[0].images?.length, 1)
  assert.equal(messages[0].dataAttachments?.length, 1)
  assert.equal(messages[2].type, undefined)
  assert.equal(messages[2].content, 'Follow up question')
})
