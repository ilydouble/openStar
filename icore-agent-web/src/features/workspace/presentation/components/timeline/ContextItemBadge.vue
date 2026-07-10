<template>
  <article
    class="w-full overflow-hidden rounded-lg border border-dashed border-zinc-300 bg-zinc-50/80 text-xs text-zinc-600 dark:border-white/15 dark:bg-white/[0.035] dark:text-zinc-300"
  >
    <button
      type="button"
      class="flex min-h-11 w-full items-center gap-2.5 px-4 py-2.5 text-left outline-none transition hover:bg-zinc-100/70 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-zinc-500/60 dark:hover:bg-white/[0.04]"
      :aria-expanded="expanded"
      :title="t('chat.toggleItemDetails')"
      @click="expanded = !expanded"
    >
      <Database :size="15" class="shrink-0 text-zinc-500 dark:text-zinc-400" aria-hidden="true" />
      <span class="min-w-0 flex-1">
        <span class="font-semibold text-zinc-700 dark:text-zinc-200">{{ t('chat.context') }}</span>
        <span class="ml-1.5 text-zinc-500 dark:text-zinc-400">· {{ kindLabel }}</span>
      </span>
      <ChevronDown
        :size="15"
        class="shrink-0 text-zinc-400 transition-transform duration-200"
        :class="expanded ? '' : '-rotate-90'"
        aria-hidden="true"
      />
    </button>
    <p
      v-if="expanded"
      class="whitespace-pre-wrap break-words border-t border-dashed border-zinc-300 px-4 py-3 leading-5 text-zinc-600 dark:border-white/10 dark:text-zinc-400"
    >
      {{ content }}
    </p>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, Database } from 'lucide-vue-next'

import type { ContextTimelineItem } from '../../../domain/models/timeline'

const props = defineProps<{ item: ContextTimelineItem }>()

const { t } = useI18n()
const expanded = ref(false)
const kindLabel = computed(() => props.item.payload.kind.replace(/[_-]+/g, ' '))
const content = computed(() => props.item.payload.content)
</script>
