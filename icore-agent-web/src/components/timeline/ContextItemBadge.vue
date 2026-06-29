<template>
  <div class="flex justify-center">
    <details class="max-w-2xl rounded-lg border border-zinc-200/80 bg-zinc-50/80 px-3 py-2 text-xs text-zinc-500 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-400">
      <summary class="cursor-pointer font-medium">
        {{ kind }}
      </summary>
      <p class="mt-2 whitespace-pre-wrap break-words leading-relaxed">
        {{ content }}
      </p>
    </details>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
})

const kind = computed(() => String(props.item?.payload?.kind || 'context'))
const content = computed(() => String(props.item?.payload?.content || ''))
</script>
