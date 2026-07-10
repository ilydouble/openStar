<template>
  <div class="flex max-w-[min(92%,calc(100vw-2.5rem))] gap-2 min-[390px]:max-w-[80%] sm:gap-3">
    <div
      class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-xs font-bold text-white shadow-md shadow-violet-900/20 dark:shadow-violet-900/40"
    >
      A
    </div>
    <div
      :class="[
        'min-w-0 rounded-2xl rounded-tl-sm border px-4 py-3 text-sm leading-relaxed shadow-md ring-1 transition-colors duration-300 dark:shadow-lg dark:backdrop-blur-sm',
        'border-zinc-200/90 bg-white text-zinc-950 ring-black/5 dark:border-white/[0.08] dark:bg-zinc-900/60 dark:text-zinc-200 dark:shadow-black/25 dark:ring-white/10',
        dark ? 'prose-chat-dark' : 'prose-chat',
        streaming ? (dark ? 'typing-cursor typing-cursor-dark' : 'typing-cursor') : '',
      ]"
    >
      <span v-if="streaming" class="whitespace-pre-wrap">{{ text }}</span>
      <span v-else v-html="html" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../../../../../shared/html/sanitizeHtml'

const props = defineProps({
  item: { type: Object, required: true },
  dark: { type: Boolean, default: false },
})

const text = computed(() => String(props.item?.payload?.text || ''))
const streaming = computed(() => props.item?.status === 'in_progress')
const html = computed(() => renderMarkdown(text.value))
</script>
