<template>
  <div v-if="text" class="flex max-w-[min(92%,calc(100vw-2.5rem))] justify-start">
    <div class="w-full max-w-2xl rounded-xl border border-violet-200/80 bg-violet-50/70 px-3 py-2 text-xs text-violet-900 ring-1 ring-violet-200/60 dark:border-violet-400/15 dark:bg-violet-950/20 dark:text-violet-200 dark:ring-violet-400/10">
      <button type="button" class="flex w-full items-center gap-1.5 text-left font-medium" @click="collapsed = !collapsed">
        <span class="transition-transform" :class="collapsed ? '' : 'rotate-90'">▸</span>
        <span>{{ t('chat.plan') }}</span>
      </button>
      <p v-if="!collapsed" class="mt-2 whitespace-pre-wrap break-words leading-relaxed">
        {{ text }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  item: { type: Object, required: true },
})

const { t } = useI18n()
const collapsed = ref(false)
const text = computed(() => String(props.item?.payload?.text || '').trim())
</script>
