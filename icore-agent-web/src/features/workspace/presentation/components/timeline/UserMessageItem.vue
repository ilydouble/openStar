<template>
  <div
    v-if="visible"
    :class="[
      'rounded-2xl rounded-tr-sm text-sm leading-relaxed ring-1 transition-colors duration-300',
      usesAttachmentLayout
        ? 'w-fit max-w-[min(24rem,calc(100vw-2.5rem))] px-2 py-1.5 shadow-sm shadow-zinc-900/5 dark:shadow-md dark:shadow-black/20'
        : 'max-w-[min(88%,calc(100vw-2.5rem))] px-3 py-3 shadow-md shadow-zinc-900/8 min-[390px]:px-4 sm:max-w-[70%] dark:shadow-lg dark:shadow-black/25',
      'bg-white text-zinc-900 ring-zinc-200/90 dark:bg-zinc-800 dark:text-zinc-100 dark:ring-white/10',
    ]"
  >
    <div v-if="usesAttachmentLayout" class="flex flex-col gap-1.5">
      <div v-if="images.length" class="flex flex-wrap items-end gap-1.5">
        <a
          v-for="image in images"
          :key="image.file_uuid"
          :href="image.content"
          target="_blank"
          rel="noopener noreferrer"
          :title="image.filename"
          class="block h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-zinc-200/90 shadow-sm ring-1 ring-zinc-200/80 outline-none transition hover:ring-violet-400/50 focus-visible:ring-2 focus-visible:ring-violet-500/60 dark:bg-zinc-700/50 dark:ring-white/10 dark:hover:ring-violet-400/35"
        >
          <img
            :src="image.content"
            :alt="image.filename"
            class="h-full w-full object-cover"
            loading="lazy"
          />
        </a>
      </div>
      <div v-if="dataAttachments.length" class="flex flex-wrap items-end gap-1.5">
        <button
          v-for="row in dataAttachments"
          :key="row.file_uuid"
          type="button"
          class="flex h-14 max-w-[11rem] shrink-0 items-center gap-2 rounded-lg border border-zinc-200/90 bg-zinc-50 px-2.5 text-left shadow-sm ring-1 ring-zinc-200/70 outline-none transition hover:ring-violet-400/50 focus-visible:ring-2 focus-visible:ring-violet-500/60 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-zinc-900/50 dark:ring-white/10 dark:hover:ring-violet-400/35"
          :disabled="!row.file_uuid"
          :title="row.filename"
          @click="$emit('open-document', row)"
        >
          <DocumentFileIcon :filename="row.filename" />
          <span class="min-w-0 flex-1 truncate text-[11px] font-medium leading-tight text-zinc-800 dark:text-zinc-200">
            {{ row.filename }}
          </span>
        </button>
      </div>
      <p
        v-if="caption"
        class="max-w-full whitespace-pre-wrap break-words border-t border-zinc-200/80 pt-1.5 text-sm leading-snug text-zinc-800 dark:border-white/10 dark:text-white/95"
      >
        {{ caption }}
      </p>
    </div>
    <template v-else>
      {{ displayText }}
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DocumentFileIcon from '../DocumentFileIcon.vue'
import { isAutoAttachmentPrompt } from '../../models/sessionMessageHydration'
import { resolveUserMessageDisplayContent } from '../../../application/services/scenarioPrompt'
import { userMessageText } from '../../models/sessionTimeline'
import type { TimelineItem } from '../../../domain/models/timeline'
import type { WorkspaceAttachment } from '../../models/viewModels'

const props = withDefaults(defineProps<{
  item: TimelineItem
  attachments?: WorkspaceAttachment[]
  templateLabels?: Record<string, string>
}>(), { attachments: () => [], templateLabels: () => ({}) })

defineEmits<{ 'open-document': [attachment: WorkspaceAttachment] }>()

const payload = computed(() => props.item?.payload || {})
const metadata = computed<Record<string, any>>(() => {
  const raw = payload.value.metadata
  return raw && typeof raw === 'object' ? raw : {}
})
const text = computed(() => userMessageText(payload.value))
const displayText = computed(() =>
  resolveUserMessageDisplayContent(
    { content: text.value, metadata: metadata.value },
    props.templateLabels,
  ),
)
const attachmentRefs = computed<WorkspaceAttachment[]>(() => {
  const uuids: unknown[] = Array.isArray(metadata.value.file_uuids)
    ? metadata.value.file_uuids
    : []
  return uuids
    .map((uuid: unknown) =>
      props.attachments.find((item: WorkspaceAttachment) => item.file_uuid === String(uuid)),
    )
    .filter((item): item is WorkspaceAttachment => Boolean(item))
})
const images = computed(() =>
  attachmentRefs.value
    .filter((item: WorkspaceAttachment) =>
      item.mode === 'image' || String(item.content_type || '').startsWith('image/'),
    )
    .map((item: WorkspaceAttachment) => ({
      file_uuid: item.file_uuid,
      content: item.download_url || '',
      filename: item.original_filename || item.filename || 'image',
    }))
    .filter((item: { content: string }) => item.content),
)
const dataAttachments = computed(() =>
  attachmentRefs.value
    .filter((item: WorkspaceAttachment) =>
      !(item.mode === 'image' || String(item.content_type || '').startsWith('image/')),
    )
    .map((item: WorkspaceAttachment) => ({
      file_uuid: item.file_uuid,
      filename: item.original_filename || item.filename || 'file',
    })),
)
const usesAttachmentLayout = computed(() => images.value.length > 0 || dataAttachments.value.length > 0)
const caption = computed(() => {
  const saved = String(metadata.value.display_caption || '').trim()
  if (saved) return saved
  const raw = text.value.trim()
  if (!raw || isAutoAttachmentPrompt(raw)) return ''
  return raw
})
const visible = computed(() => usesAttachmentLayout.value || Boolean(displayText.value.trim()))
</script>
