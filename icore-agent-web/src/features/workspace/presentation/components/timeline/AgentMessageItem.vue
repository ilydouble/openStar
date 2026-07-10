<template>
  <div class="flex w-full max-w-[min(94%,calc(100vw-2rem))] items-start gap-2.5 sm:max-w-[82%] sm:gap-3">
    <div
      class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-600 text-xs font-bold text-white shadow-sm shadow-violet-900/20 dark:bg-violet-500 dark:shadow-violet-900/40"
    >
      A
    </div>
    <div
      :class="[
        'min-w-0 flex-1 rounded-2xl rounded-tl-md border px-4 py-3 text-sm leading-6 shadow-sm ring-1 transition-colors duration-300 dark:shadow-md',
        'border-zinc-200/90 bg-white text-zinc-950 ring-black/[0.04] dark:border-white/[0.08] dark:bg-zinc-900/65 dark:text-zinc-200 dark:shadow-black/20 dark:ring-white/[0.06]',
        dark ? 'prose-chat-dark' : 'prose-chat',
        streaming ? (dark ? 'typing-cursor typing-cursor-dark' : 'typing-cursor') : '',
      ]"
    >
      <span v-if="streaming" class="whitespace-pre-wrap">{{ text }}</span>
      <span v-else v-html="html" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '../../../../../shared/presentation/html/sanitizeHtml'
import type { AgentMessageTimelineItem } from '../../../domain/models/timeline'

const props = withDefaults(defineProps<{
  item: AgentMessageTimelineItem
  dark?: boolean
}>(), { dark: false })

const text = computed(() => props.item.payload.text)
const streaming = computed(() => props.item.status === 'in_progress')
const html = computed(() => renderMarkdown(text.value))
</script>
