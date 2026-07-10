// @vitest-environment jsdom

import assert from 'node:assert/strict'
import { test } from 'vitest'
import { mount, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'

import enUS from '../../../../../shared/presentation/i18n/locales/en-US'
import type {
  AgentMessageTimelineItem,
  PlanTimelineItem,
  ReasoningTimelineItem,
  TimelineItem as TimelineItemModel,
  ToolCallTimelineItem,
} from '../../../domain/models/timeline'
import AgentMessageItem from './AgentMessageItem.vue'
import ContextItemBadge from './ContextItemBadge.vue'
import PlanItem from './PlanItem.vue'
import ReasoningItem from './ReasoningItem.vue'
import TimelineItem from './TimelineItem.vue'
import ToolCallItem from './ToolCallItem.vue'
import UserMessageItem from './UserMessageItem.vue'

const i18n = createI18n({ legacy: false, locale: 'en-US', messages: { 'en-US': enUS } })

const timelineItems: TimelineItemModel[] = [
  {
    itemId: 'context-1',
    type: 'context',
    status: 'completed',
    payload: { type: 'context', status: 'completed', kind: 'user_memory', content: 'Context' },
  },
  {
    itemId: 'user-1',
    type: 'user_message',
    status: 'completed',
    payload: {
      type: 'user_message',
      status: 'completed',
      content: [{ type: 'text', text: 'Question' }],
      metadata: {},
    },
  },
  {
    itemId: 'agent-1',
    type: 'agent_message',
    status: 'completed',
    payload: { type: 'agent_message', status: 'completed', text: 'Answer' },
  },
  {
    itemId: 'reasoning-1',
    type: 'reasoning',
    status: 'completed',
    payload: { type: 'reasoning', status: 'completed', text: 'Reasoning' },
  },
  {
    itemId: 'plan-1',
    type: 'plan',
    status: 'completed',
    payload: { type: 'plan', status: 'completed', text: 'Step one' },
  },
  {
    itemId: 'tool-1',
    type: 'tool_call',
    status: 'completed',
    payload: {
      type: 'tool_call',
      status: 'completed',
      function: { name: 'web_search', arguments_text: '{}', arguments_json: {} },
    },
  },
]

const componentByType = {
  context: ContextItemBadge,
  user_message: UserMessageItem,
  agent_message: AgentMessageItem,
  reasoning: ReasoningItem,
  plan: PlanItem,
  tool_call: ToolCallItem,
}

test('TimelineItem dispatches every current protocol item to its presentation component', () => {
  for (const item of timelineItems) {
    const wrapper = shallowMount(TimelineItem, { props: { item } })
    assert.equal(wrapper.findComponent(componentByType[item.type]).exists(), true)
  }
})

test('TimelineItem aligns user messages right and agent messages left', () => {
  const user = shallowMount(TimelineItem, { props: { item: timelineItems[1] } })
  const agent = shallowMount(TimelineItem, { props: { item: timelineItems[2] } })

  assert.equal(user.classes().includes('justify-end'), true)
  assert.equal(agent.classes().includes('justify-start'), true)
})

test('AgentMessageItem starts the bubble at the timeline edge without an avatar', () => {
  const wrapper = shallowMount(AgentMessageItem, {
    props: { item: timelineItems[2] as AgentMessageTimelineItem },
  })

  assert.equal(wrapper.element.children.length, 1)
  assert.equal(wrapper.find('.rounded-full').exists(), false)
  assert.equal(wrapper.get('[data-testid="agent-message-bubble"]').classes().includes('w-full'), true)
})

test('ReasoningItem expands while streaming and collapses when completed', async () => {
  const running: ReasoningTimelineItem = {
    itemId: 'reasoning-live',
    type: 'reasoning',
    status: 'in_progress',
    payload: {
      type: 'reasoning',
      status: 'in_progress',
      text: 'Inspect the evidence.\nCompare the sources.',
    },
  }
  const wrapper = mount(ReasoningItem, {
    props: { item: running },
    global: { plugins: [i18n] },
  })

  assert.equal(wrapper.find('button').attributes('aria-expanded'), 'true')
  assert.equal(wrapper.text().includes('Compare the sources.'), true)

  await wrapper.setProps({
    item: {
      ...running,
      status: 'completed',
      payload: { ...running.payload, status: 'completed' },
    },
  })
  assert.equal(wrapper.find('button').attributes('aria-expanded'), 'false')
  assert.equal(wrapper.text().includes('Compare the sources.'), false)

  await wrapper.find('button').trigger('click')
  assert.equal(wrapper.text().includes('Compare the sources.'), true)
})

test('PlanItem renders protocol text as a counted, full-width step list', () => {
  const item: PlanTimelineItem = {
    itemId: 'plan-steps',
    type: 'plan',
    status: 'completed',
    payload: {
      type: 'plan',
      status: 'completed',
      text: '- Find sources\n- Compare signals\n- Prepare report',
    },
  }
  const wrapper = mount(PlanItem, {
    props: { item },
    global: { plugins: [i18n] },
  })

  assert.equal(wrapper.classes().includes('w-full'), true)
  assert.equal(wrapper.text().includes('Plan · 3 step(s)'), true)
  assert.equal(wrapper.findAll('li').length, 3)
})

test('ToolCallItem localizes known tools and keeps raw details available', async () => {
  const item: ToolCallTimelineItem = {
    itemId: 'tool-completed',
    type: 'tool_call',
    status: 'completed',
    payload: {
      type: 'tool_call',
      status: 'completed',
      function: {
        name: 'web_search',
        arguments_text: '{"query":"competitor updates"}',
        arguments_json: { query: 'competitor updates' },
      },
      result: { content: 'Collected eight pages.', structured_content: null },
    },
  }
  const wrapper = mount(ToolCallItem, {
    props: { item },
    global: { plugins: [i18n] },
  })

  assert.equal(wrapper.text().includes('Web research'), true)
  assert.equal(wrapper.text().includes('Completed'), true)
  assert.equal(wrapper.find('button').attributes('aria-expanded'), 'false')

  await wrapper.find('button').trigger('click')
  assert.equal(wrapper.find('pre').text().includes('competitor updates'), true)
  assert.equal(wrapper.text().includes('Collected eight pages.'), true)
})
