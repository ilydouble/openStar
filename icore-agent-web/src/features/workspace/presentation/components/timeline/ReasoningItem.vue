<template>
  <article
    v-if="text"
    class="w-full overflow-hidden rounded-lg border border-cyan-300/70 bg-cyan-50/80 text-xs text-cyan-950 shadow-sm ring-1 ring-cyan-200/50 dark:border-cyan-400/30 dark:bg-cyan-950/35 dark:text-cyan-100 dark:ring-cyan-400/10"
    :data-status="item.status"
  >
    <button
      type="button"
      class="flex min-h-12 w-full items-center gap-2.5 px-4 py-3 text-left outline-none transition hover:bg-cyan-100/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-500/70 dark:hover:bg-cyan-900/20"
      :aria-expanded="!collapsed"
      :title="t('chat.toggleItemDetails')"
      @click="collapsed = !collapsed"
    >
      <BrainCircuit :size="17" class="shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden="true" />
      <span class="min-w-0 flex-1">
        <span class="font-semibold">{{ t('chat.reasoning') }}</span>
        <span v-if="isStreaming" class="ml-1.5 text-cyan-700 dark:text-cyan-300">
          {{ t('chat.reasoningLive') }}
        </span>
        <span
          v-else-if="collapsed && preview"
          class="ml-1.5 text-cyan-700/80 dark:text-cyan-200/70"
        >
          · {{ preview }}
        </span>
      </span>
      <LoaderCircle
        v-if="isStreaming"
        :size="15"
        class="shrink-0 animate-spin text-cyan-600 dark:text-cyan-300"
        aria-hidden="true"
      />
      <ChevronDown
        :size="16"
        class="shrink-0 text-cyan-700/70 transition-transform duration-200 dark:text-cyan-300/70"
        :class="collapsed ? '-rotate-90' : ''"
        aria-hidden="true"
      />
    </button>
    <p
      v-if="!collapsed"
      class="whitespace-pre-wrap break-words border-t border-cyan-300/50 px-4 py-3 text-[13px] leading-6 text-cyan-950/85 dark:border-cyan-400/20 dark:text-cyan-100/80"
    >
      {{ text }}
    </p>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { BrainCircuit, ChevronDown, LoaderCircle } from 'lucide-vue-next'

import type { ReasoningTimelineItem } from '../../../domain/models/timeline'

const props = defineProps<{ item: ReasoningTimelineItem }>()

const { t } = useI18n()
const collapsed = ref(isTerminalStatus(props.item.status))
const text = computed(() => props.item.payload.text.trim())
const isStreaming = computed(() => !isTerminalStatus(props.item.status))
const preview = computed(() => {
  const firstLine = text.value.split('\n').find((line) => line.trim()) || ''
  return firstLine.length > 72 ? `${firstLine.slice(0, 69)}...` : firstLine
})

watch(
  () => props.item.status,
  (nextStatus) => {
    collapsed.value = isTerminalStatus(nextStatus)
  },
)

/** Return whether reasoning streaming has reached a terminal state. */
function isTerminalStatus(status: string): boolean {
  return status === 'completed' || status === 'failed'
}
</script>
