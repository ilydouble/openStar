<template>
  <svg
    :class="[sizeClass, colorClass]"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <!-- Word -->
    <template v-if="kind === 'word'">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M9 3.5H15.2L19 7.3V20.5A1.5 1.5 0 0117.5 22H6.5A1.5 1.5 0 015 20.5V5A1.5 1.5 0 016.5 3.5H9Z"
      />
      <path stroke-linecap="round" d="M15 3.5V7.5H19" />
      <path stroke-linecap="round" d="M8 11H16M8 14H16M8 17H13" />
      <path stroke-linecap="round" stroke-linejoin="round" d="M8.5 8.2H10.8L11.8 10.9L12.8 8.2H15" />
    </template>

    <!-- Excel -->
    <template v-else-if="kind === 'excel'">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M9 3.5H15.2L19 7.3V20.5A1.5 1.5 0 0117.5 22H6.5A1.5 1.5 0 015 20.5V5A1.5 1.5 0 016.5 3.5H9Z"
      />
      <path stroke-linecap="round" d="M15 3.5V7.5H19" />
      <path stroke-linecap="round" d="M8 10H16V18H8V10Z" />
      <path stroke-linecap="round" d="M11 10V18M14 10V18M8 13.5H16M8 15.5H16" />
    </template>

    <!-- PDF -->
    <template v-else-if="kind === 'pdf'">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M9 3.5H15.2L19 7.3V20.5A1.5 1.5 0 0117.5 22H6.5A1.5 1.5 0 015 20.5V5A1.5 1.5 0 016.5 3.5H9Z"
      />
      <path stroke-linecap="round" d="M15 3.5V7.5H19" />
      <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 16.5H16.5V19.5H7.5V16.5Z" />
      <path stroke-linecap="round" d="M9.5 18H14.5M10.5 11H14M10.5 13.5H13.5" />
    </template>

    <!-- Plain text -->
    <template v-else-if="kind === 'text'">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M9 3.5H15.2L19 7.3V20.5A1.5 1.5 0 0117.5 22H6.5A1.5 1.5 0 015 20.5V5A1.5 1.5 0 016.5 3.5H9Z"
      />
      <path stroke-linecap="round" d="M15 3.5V7.5H19" />
      <path stroke-linecap="round" d="M8 11H16M8 14H16M8 17H14" />
      <path stroke-linecap="round" stroke-linejoin="round" d="M9.5 8.2H11.5V9.8H9.5V8.2Z" />
    </template>

    <!-- Markdown -->
    <template v-else-if="kind === 'markdown'">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M9 3.5H15.2L19 7.3V20.5A1.5 1.5 0 0117.5 22H6.5A1.5 1.5 0 015 20.5V5A1.5 1.5 0 016.5 3.5H9Z"
      />
      <path stroke-linecap="round" d="M15 3.5V7.5H19" />
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 11.5L10.6 15.5L12 12.8L13.4 15.5L15 11.5" />
      <path stroke-linecap="round" d="M8 17H16" />
    </template>

    <!-- Generic document -->
    <template v-else>
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </template>
  </svg>
</template>

<script setup>
import { computed } from 'vue'
import {
  DOCUMENT_FILE_ICON_COLORS,
  resolveDocumentFileKind,
} from '../../presentation/models/documentFileType'

const props = defineProps({
  filename: { type: String, default: '' },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md'].includes(value),
  },
})

const kind = computed(() => resolveDocumentFileKind(props.filename))
const sizeClass = computed(() =>
  props.size === 'sm' ? 'h-3.5 w-3.5 shrink-0' : 'h-7 w-7 shrink-0',
)
const colorClass = computed(() => DOCUMENT_FILE_ICON_COLORS[kind.value])
</script>
