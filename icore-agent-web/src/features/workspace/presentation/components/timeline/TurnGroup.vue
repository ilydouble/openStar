<template>
  <section v-if="visibleItems.length" class="space-y-4">
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

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TimelineItem from './TimelineItem.vue'
import { isVisibleTimelineItem } from '../../models/sessionTimeline'
import type { TimelineTurn } from '../../../domain/models/timeline'
import type { WorkspaceAttachment } from '../../models/viewModels'

const props = withDefaults(defineProps<{
  turn: TimelineTurn
  attachments?: WorkspaceAttachment[]
  dark?: boolean
  showContext?: boolean
  templateLabels?: Record<string, string>
}>(), {
  attachments: () => [],
  dark: false,
  showContext: false,
  templateLabels: () => ({}),
})

defineEmits<{ 'open-document': [attachment: WorkspaceAttachment] }>()

const { t } = useI18n()
const visibleItems = computed(() =>
  (props.turn.items || []).filter((item) =>
    isVisibleTimelineItem(item, { showContext: props.showContext }),
  ),
)
const errorText = computed(() =>
  String(readTurnError(props.turn.error) || t('chat.requestFailed', { msg: 'Agent turn failed' })),
)

/** Read a stable message from an unknown turn failure payload. */
function readTurnError(error: unknown): string {
  if (!error || typeof error !== 'object') return ''
  const record = error as Record<string, unknown>
  return String(record.message || record.code || '')
}
</script>
