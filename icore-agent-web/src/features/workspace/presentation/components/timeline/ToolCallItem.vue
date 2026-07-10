<template>
  <div class="flex max-w-[min(92%,calc(100vw-2.5rem))] justify-start">
    <div class="w-full max-w-2xl rounded-xl border border-zinc-200/90 bg-white/70 px-3 py-2 text-xs ring-1 ring-black/5 dark:border-white/[0.08] dark:bg-zinc-900/40 dark:ring-white/10">
      <button
        type="button"
        class="flex w-full items-center justify-between gap-3 text-left text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
        @click="collapsed = !collapsed"
      >
        <span class="flex min-w-0 items-center gap-2">
          <span class="transition-transform" :class="collapsed ? '' : 'rotate-90'">▸</span>
          <span class="truncate font-medium text-zinc-800 dark:text-zinc-200">{{ toolName }}</span>
        </span>
        <span :class="statusClass">{{ statusLabel }}</span>
      </button>
      <div v-if="!collapsed" class="mt-2 space-y-2 border-l border-zinc-200 pl-3 dark:border-white/10">
        <pre v-if="argsPreview" class="max-h-32 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-100 px-2 py-1.5 text-[11px] text-zinc-700 dark:bg-black/20 dark:text-zinc-300">{{ argsPreview }}</pre>
        <p v-if="resultText" class="whitespace-pre-wrap break-words text-zinc-600 dark:text-zinc-400">
          {{ resultText }}
        </p>
        <p v-if="errorText" class="whitespace-pre-wrap break-words text-red-600 dark:text-red-300">
          {{ errorText }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
})

const collapsed = ref(props.item?.status === 'completed')
const payload = computed(() => props.item?.payload || {})
const fn = computed(() => payload.value.function || {})
const toolName = computed(() => String(fn.value.name || 'tool'))
const statusLabel = computed(() => String(props.item?.status || payload.value.status || 'running'))
const statusClass = computed(() => {
  if (statusLabel.value === 'failed') return 'shrink-0 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-600 dark:bg-red-900/25 dark:text-red-300'
  if (statusLabel.value === 'completed') return 'shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-900/25 dark:text-emerald-300'
  return 'shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-900/25 dark:text-amber-300'
})
const argsPreview = computed(() => {
  const text = String(fn.value.arguments_text || '').trim()
  if (text) return text
  const json = fn.value.arguments_json
  if (!json || typeof json !== 'object') return ''
  try {
    return JSON.stringify(json, null, 2)
  } catch {
    return ''
  }
})
const resultText = computed(() => String(payload.value.result?.content || '').trim())
const errorText = computed(() => String(payload.value.error?.message || '').trim())

watch(
  () => props.item?.status,
  (status) => {
    if (status === 'completed') collapsed.value = true
    if (status === 'running' || status === 'in_progress') collapsed.value = false
  },
)
</script>
