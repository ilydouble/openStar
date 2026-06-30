<template>
  <section v-if="visibleItems.length" class="space-y-3">
    <TimelineItem
      v-for="item in visibleItems"
      :key="item.itemId"
      :item="item"
      :attachments="attachments"
      :dark="dark"
      :template-labels="templateLabels"
      @open-document="$emit('open-document', $event)"
    />
    <div
      v-if="turn.status === 'failed'"
      class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-400/20 dark:bg-red-900/20 dark:text-red-300"
    >
      {{ errorText }}
    </div>
    <div
      v-else-if="turn.status === 'aborted' || turn.status === 'interrupted'"
      class="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-400"
    >
      {{ t('chat.turnAborted') }}
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TimelineItem from './TimelineItem.vue'
import { isVisibleTimelineItem } from '../../utils/sessionTimeline.js'

const props = defineProps({
  turn: { type: Object, required: true },
  attachments: { type: Array, default: () => [] },
  dark: { type: Boolean, default: false },
  showContext: { type: Boolean, default: false },
  templateLabels: { type: Object, default: () => ({}) },
})

defineEmits(['open-document'])

const { t } = useI18n()
const visibleItems = computed(() =>
  (props.turn.items || []).filter((item) =>
    isVisibleTimelineItem(item, { showContext: props.showContext }),
  ),
)
const errorText = computed(() =>
  String(props.turn.error?.message || props.turn.error?.code || t('chat.requestFailed', { msg: 'Agent turn failed' })),
)
</script>
