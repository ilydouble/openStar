<template>
  <div class="mx-auto w-full max-w-3xl space-y-6">
    <TurnGroup
      v-for="turn in visibleTurns"
      :key="turn.turnId"
      :turn="turn"
      :attachments="resolvedAttachments"
      :dark="dark"
      :show-context="showContext"
      :template-labels="templateLabels"
      @open-document="$emit('open-document', $event)"
    />
    <div v-if="showLoadingIndicator" class="flex justify-start gap-3 pt-2">
      <div
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600"
      >
        <span class="text-xs font-bold text-white">A</span>
      </div>
      <div
        class="flex items-center gap-1 rounded-2xl border border-zinc-200/90 bg-white px-4 py-3 shadow-md ring-1 ring-black/5 transition-colors duration-300 dark:border-white/[0.08] dark:bg-zinc-900/60 dark:shadow-lg dark:shadow-black/20 dark:ring-white/10"
      >
        <span
          v-for="i in 3"
          :key="i"
          class="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 dark:bg-zinc-500"
          :style="{ animationDelay: `${(i - 1) * 0.15}s` }"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import TurnGroup from './TurnGroup.vue'
import { isVisibleTimelineItem } from '../../../presentation/models/sessionTimeline'

const props = defineProps({
  timeline: { type: Object, required: true },
  attachments: { type: Array, default: null },
  loading: { type: Boolean, default: false },
  dark: { type: Boolean, default: false },
  showContext: { type: Boolean, default: false },
  templateLabels: { type: Object, default: () => ({}) },
})

defineEmits(['open-document'])

const visibleTurns = computed(() =>
  (props.timeline?.turns || []).filter((turn) =>
    (turn.items || []).some((item) =>
      isVisibleTimelineItem(item, { showContext: props.showContext }),
    ),
  ),
)
const resolvedAttachments = computed(() =>
  Array.isArray(props.attachments) ? props.attachments : props.timeline?.attachments || [],
)
const activeTurnHasVisibleOutput = computed(() => {
  const active = visibleTurns.value.at(-1)
  if (!active) return false
  return (active.items || []).some((item) => {
    if (item.type === 'context') return false
    if (item.type === 'agent_message') return Boolean(String(item.payload?.text || '').trim())
    return item.type === 'tool_call' || item.type === 'reasoning' || item.type === 'plan'
  })
})
const showLoadingIndicator = computed(() => props.loading && !activeTurnHasVisibleOutput.value)
</script>
