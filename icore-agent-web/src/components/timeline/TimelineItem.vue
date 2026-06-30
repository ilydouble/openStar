<template>
  <div :class="rowClass">
    <UserMessageItem
      v-if="item.type === 'user_message'"
      :item="item"
      :attachments="attachments"
      :template-labels="templateLabels"
      @open-document="$emit('open-document', $event)"
    />
    <AgentMessageItem
      v-else-if="item.type === 'agent_message'"
      :item="item"
      :dark="dark"
    />
    <ToolCallItem v-else-if="item.type === 'tool_call'" :item="item" />
    <ReasoningItem v-else-if="item.type === 'reasoning'" :item="item" />
    <PlanItem v-else-if="item.type === 'plan'" :item="item" />
    <ContextItemBadge v-else-if="item.type === 'context'" :item="item" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AgentMessageItem from './AgentMessageItem.vue'
import ContextItemBadge from './ContextItemBadge.vue'
import PlanItem from './PlanItem.vue'
import ReasoningItem from './ReasoningItem.vue'
import ToolCallItem from './ToolCallItem.vue'
import UserMessageItem from './UserMessageItem.vue'

const props = defineProps({
  item: { type: Object, required: true },
  attachments: { type: Array, default: () => [] },
  dark: { type: Boolean, default: false },
  templateLabels: { type: Object, default: () => ({}) },
})

defineEmits(['open-document'])

const rowClass = computed(() => {
  if (props.item.type === 'user_message') return 'flex justify-end'
  if (props.item.type === 'context') return 'flex justify-center'
  return 'flex justify-start'
})
</script>
