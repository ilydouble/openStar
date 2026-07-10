<template>
  <article
    v-if="steps.length"
    class="w-full overflow-hidden rounded-lg border border-violet-300/70 bg-violet-50/80 text-xs text-violet-950 shadow-sm ring-1 ring-violet-200/50 dark:border-violet-400/30 dark:bg-violet-950/35 dark:text-violet-100 dark:ring-violet-400/10"
  >
    <button
      type="button"
      class="flex min-h-12 w-full items-center gap-2.5 px-4 py-3 text-left outline-none transition hover:bg-violet-100/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-violet-500/70 dark:hover:bg-violet-900/20"
      :aria-expanded="!collapsed"
      :title="t('chat.toggleItemDetails')"
      @click="collapsed = !collapsed"
    >
      <ListChecks :size="17" class="shrink-0 text-violet-700 dark:text-violet-300" aria-hidden="true" />
      <span class="min-w-0 flex-1 font-semibold">
        {{ t('chat.planWithSteps', { count: steps.length }) }}
      </span>
      <ChevronDown
        :size="16"
        class="shrink-0 text-violet-700/70 transition-transform duration-200 dark:text-violet-300/70"
        :class="collapsed ? '-rotate-90' : ''"
        aria-hidden="true"
      />
    </button>
    <ol
      v-if="!collapsed"
      class="space-y-2 border-t border-violet-300/50 px-4 py-3 text-[13px] leading-5 text-violet-950/85 dark:border-violet-400/20 dark:text-violet-100/80"
    >
      <li v-for="(step, index) in steps" :key="`${index}-${step}`" class="flex gap-2.5">
        <span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500 dark:bg-violet-300" />
        <span class="min-w-0 break-words">{{ step }}</span>
      </li>
    </ol>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, ListChecks } from 'lucide-vue-next'

import type { PlanTimelineItem } from '../../../domain/models/timeline'

const props = defineProps<{ item: PlanTimelineItem }>()

const { t } = useI18n()
const collapsed = ref(false)
const steps = computed(() => props.item.payload.text
  .split('\n')
  .map((line) => line.trim().replace(/^(?:[-*\u2022]|\d+[.)])\s*/, ''))
  .filter(Boolean))
</script>
