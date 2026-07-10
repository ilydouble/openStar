<template>
  <div v-if="text" class="flex max-w-[min(92%,calc(100vw-2.5rem))] justify-start">
    <div class="w-full max-w-2xl rounded-xl border border-sky-200/80 bg-sky-50/70 px-3 py-2 text-xs text-sky-900 ring-1 ring-sky-200/60 dark:border-sky-400/15 dark:bg-sky-950/20 dark:text-sky-200 dark:ring-sky-400/10">
      <button type="button" class="flex w-full items-center gap-1.5 text-left font-medium" @click="collapsed = !collapsed">
        <span class="transition-transform" :class="collapsed ? '' : 'rotate-90'">▸</span>
        <span>{{ t('chat.reasoning') }}</span>
      </button>
      <p v-if="!collapsed" class="mt-2 whitespace-pre-wrap break-words leading-relaxed">
        {{ text }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  item: { type: Object, required: true },
})

const { t } = useI18n()
const collapsed = ref(true)
const text = computed(() => String(props.item?.payload?.text || '').trim())
</script>
