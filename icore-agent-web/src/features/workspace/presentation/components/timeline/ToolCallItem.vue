<template>
  <article
    class="w-full overflow-hidden rounded-lg border border-zinc-200/90 bg-white/80 text-xs shadow-sm ring-1 ring-black/[0.03] dark:border-white/[0.08] dark:bg-zinc-900/55 dark:ring-white/[0.06]"
    :data-status="status"
  >
    <button
      type="button"
      class="flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left outline-none transition hover:bg-zinc-50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-violet-500/70 dark:hover:bg-white/[0.03]"
      :aria-expanded="!collapsed"
      :title="t('chat.toggleItemDetails')"
      @click="collapsed = !collapsed"
    >
      <span
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-zinc-100 text-zinc-600 dark:bg-white/[0.06] dark:text-zinc-300"
      >
        <component :is="presentation.icon" :size="16" aria-hidden="true" />
      </span>
      <span class="min-w-0 flex-1">
        <span class="flex min-w-0 flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
          <span class="font-semibold text-zinc-900 dark:text-zinc-100">{{ toolLabel }}</span>
          <span v-if="callSummary" class="truncate text-zinc-500 dark:text-zinc-400">
            · {{ callSummary }}
          </span>
        </span>
        <span
          v-if="collapsed && resultSummary"
          class="mt-1 block truncate text-[11px] leading-4 text-zinc-500 dark:text-zinc-400"
        >
          {{ resultSummary }}
        </span>
      </span>
      <span :class="statusClass">
        <component
          :is="statusIcon"
          :size="13"
          :class="isActive ? 'animate-spin' : ''"
          aria-hidden="true"
        />
        {{ statusLabel }}
      </span>
      <ChevronDown
        :size="16"
        class="shrink-0 text-zinc-400 transition-transform duration-200"
        :class="collapsed ? '-rotate-90' : ''"
        aria-hidden="true"
      />
    </button>

    <div
      v-if="!collapsed"
      class="space-y-3 border-t border-zinc-200/80 px-4 py-3 dark:border-white/[0.07]"
    >
      <div v-if="argsPreview">
        <p class="mb-1.5 font-medium text-zinc-500 dark:text-zinc-400">
          {{ t('chat.toolInput') }}
        </p>
        <pre class="max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-md bg-zinc-100 px-3 py-2 font-mono text-[11px] leading-5 text-zinc-700 dark:bg-black/20 dark:text-zinc-300">{{ argsPreview }}</pre>
      </div>
      <div v-if="resultText">
        <p class="mb-1.5 font-medium text-zinc-500 dark:text-zinc-400">
          {{ t('chat.toolOutput') }}
        </p>
        <p class="max-h-48 overflow-auto whitespace-pre-wrap break-words leading-5 text-zinc-700 dark:text-zinc-300">
          {{ resultText }}
        </p>
      </div>
      <p
        v-if="errorText"
        class="whitespace-pre-wrap break-words rounded-md bg-red-50 px-3 py-2 leading-5 text-red-700 dark:bg-red-950/25 dark:text-red-300"
      >
        {{ errorText }}
      </p>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Ban,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  LoaderCircle,
} from 'lucide-vue-next'

import type { ToolCallTimelineItem } from '../../../domain/models/timeline'
import {
  formatToolArguments,
  resolveToolPresentation,
  summarizeToolArguments,
  summarizeToolResult,
} from '../../models/toolPresentation'

const props = defineProps<{ item: ToolCallTimelineItem }>()

const { t } = useI18n()
const collapsed = ref(isTerminalStatus(props.item.status))
const payload = computed(() => props.item.payload)
const toolName = computed(() => String(payload.value.function.name || ''))
const presentation = computed(() => resolveToolPresentation(toolName.value))
const toolLabel = computed(() => presentation.value.labelKey
  ? t(presentation.value.labelKey)
  : presentation.value.fallbackLabel)
const status = computed(() => props.item.status || payload.value.status || 'running')
const isActive = computed(() => ['streaming', 'ready', 'running', 'in_progress'].includes(status.value))
const statusLabel = computed(() => t(`chat.toolStatus.${status.value}`))
const statusIcon = computed(() => {
  if (status.value === 'completed') return CheckCircle2
  if (status.value === 'failed') return CircleAlert
  if (status.value === 'declined') return Ban
  return LoaderCircle
})
const statusClass = computed(() => {
  const base = 'flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium'
  if (status.value === 'failed') {
    return `${base} bg-red-50 text-red-700 dark:bg-red-950/35 dark:text-red-300`
  }
  if (status.value === 'completed') {
    return `${base} bg-emerald-50 text-emerald-700 dark:bg-emerald-950/35 dark:text-emerald-300`
  }
  if (status.value === 'declined') {
    return `${base} bg-zinc-100 text-zinc-600 dark:bg-white/[0.06] dark:text-zinc-300`
  }
  return `${base} bg-amber-50 text-amber-700 dark:bg-amber-950/35 dark:text-amber-300`
})
const callSummary = computed(() => summarizeToolArguments(payload.value))
const argsPreview = computed(() => formatToolArguments(payload.value))
const resultText = computed(() => String(payload.value.result?.content || '').trim())
const resultSummary = computed(() => summarizeToolResult(payload.value))
const errorText = computed(() => String(payload.value.error?.message || '').trim())

watch(
  () => props.item.status,
  (nextStatus) => {
    collapsed.value = isTerminalStatus(nextStatus)
  },
)

/** Return whether a tool status has no more live updates. */
function isTerminalStatus(statusValue: string): boolean {
  return statusValue === 'completed' || statusValue === 'failed' || statusValue === 'declined'
}
</script>
