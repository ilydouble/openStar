<template>
  <div
    class="flex h-full flex-col bg-zinc-100 transition-colors duration-300 ease-out dark:bg-zinc-950"
  >
    <div ref="scrollEl" class="flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-6">
      <div
        v-for="msg in messages"
        :key="msg.id"
        v-show="msg.role === 'user' ? userMessageVisible(msg) : (msg.content || (msg.steps && msg.steps.length))"
        :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
      >
        <div
          v-if="msg.role === 'user'"
          :class="[
            'rounded-2xl rounded-tr-sm text-sm leading-relaxed text-zinc-900 shadow-md ring-1 ring-zinc-200/90 shadow-zinc-900/8 transition-colors duration-300 dark:bg-zinc-800 dark:text-zinc-100 dark:shadow-lg dark:shadow-black/25 dark:ring-white/10',
            userBubbleUsesAttachLayout(msg)
              ? 'w-fit max-w-[min(24rem,calc(100vw-2.5rem))] bg-white px-2 py-1.5 dark:bg-zinc-800'
              : 'max-w-[70%] bg-white px-4 py-3 dark:bg-zinc-800',
          ]"
        >
          <template v-if="msg.type === 'file'">
            <div class="flex flex-col gap-1.5">
              <div class="flex flex-wrap items-end gap-1.5">
                <div
                  v-for="(row, idx) in (msg.fileAttachments || [])"
                  :key="(row.filename || 'file') + '-' + idx"
                  class="flex h-14 max-w-[11rem] shrink-0 items-center gap-2 rounded-lg border border-zinc-200/90 bg-zinc-50 px-2.5 shadow-sm ring-1 ring-zinc-200/70 dark:border-white/10 dark:bg-zinc-900/50 dark:ring-white/10"
                  :title="row.filename"
                >
                  <DocumentFileIcon :filename="row.filename" />
                  <span class="min-w-0 flex-1 truncate text-[11px] font-medium leading-tight text-zinc-800 dark:text-zinc-200">
                    {{ row.filename }}
                  </span>
                </div>
              </div>
              <p
                v-if="msg.caption"
                class="max-w-full whitespace-pre-wrap break-words border-t border-zinc-200/80 pt-1.5 text-sm leading-snug text-zinc-800 dark:border-white/10 dark:text-white/95"
              >
                {{ msg.caption }}
              </p>
            </div>
          </template>
          <template v-else>
            {{ msg.content }}
          </template>
        </div>
        <div v-else class="flex max-w-[80%] gap-3">
          <div
            class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-xs font-bold text-white shadow-md shadow-violet-900/20 dark:shadow-violet-900/40"
          >
            A
          </div>
          <div class="flex min-w-0 flex-1 flex-col gap-2">
            <div
              v-if="msg.steps && msg.steps.length"
              class="rounded-xl border border-zinc-200/90 bg-white/70 px-3 py-2 text-xs ring-1 ring-black/5 dark:border-white/[0.08] dark:bg-zinc-900/40 dark:ring-white/10"
            >
              <button
                type="button"
                class="flex w-full items-center gap-1.5 text-left text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                @click="msg.stepsCollapsed = !msg.stepsCollapsed"
              >
                <span class="transition-transform" :class="msg.stepsCollapsed ? '' : 'rotate-90'">▸</span>
                <span>
                  {{ msg.streaming
                    ? t('chat.stepsLive', { n: msg.steps.length })
                    : t('chat.stepsCollapsed', { n: msg.steps.length }) }}
                </span>
              </button>
              <ul
                v-if="!msg.stepsCollapsed"
                class="mt-2 space-y-1 border-l border-zinc-200 pl-3 dark:border-white/10"
              >
                <li
                  v-for="s in msg.steps"
                  :key="s.step"
                  class="text-zinc-600 dark:text-zinc-400"
                >
                  <span class="font-medium text-zinc-700 dark:text-zinc-300">{{ s.step }}. {{ s.tool }}</span>
                  <span v-if="s.input_preview" class="ml-1 text-zinc-500 dark:text-zinc-500">— {{ s.input_preview }}</span>
                </li>
              </ul>
            </div>
            <div
              :class="[
                'rounded-2xl rounded-tl-sm border px-4 py-3 text-sm leading-relaxed shadow-md ring-1 transition-colors duration-300 dark:shadow-lg dark:backdrop-blur-sm',
                'border-zinc-200/90 bg-white text-zinc-950 ring-black/5 dark:border-white/[0.08] dark:bg-zinc-900/60 dark:text-zinc-200 dark:shadow-black/25 dark:ring-white/10',
                dark ? 'prose-chat-dark' : 'prose-chat',
                msg.streaming ? (dark ? 'typing-cursor typing-cursor-dark' : 'typing-cursor') : '',
              ]"
            >
              <span v-if="msg.streaming" class="whitespace-pre-wrap">{{ msg.content }}</span>
              <span v-else v-html="assistantMessageHtml(msg)" />
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="loading && (!streamingMsg || (!streamingMsg.content && !(streamingMsg.steps && streamingMsg.steps.length)))"
        class="flex justify-start gap-3"
      >
        <div
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600"
        >
          <span class="text-xs font-bold text-white">A</span>
        </div>
        <div
          class="flex items-center gap-1 rounded-2xl border border-zinc-200/90 bg-white px-4 py-3 shadow-md ring-1 ring-black/5 transition-colors duration-300 dark:border-white/[0.08] dark:bg-zinc-900/60 dark:shadow-lg dark:shadow-black/20 dark:ring-white/10"
        >
          <span
            v-for="i in 3"
            :key="i"
            class="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 dark:bg-zinc-500"
            :style="{ animationDelay: `${(i - 1) * 0.15}s` }"
          />
        </div>
      </div>
    </div>

    <div
      :class="[
        'border-t px-4 py-3 backdrop-blur-xl transition-colors duration-300 sm:px-6',
        isDraggingFile
          ? 'border-violet-400 bg-violet-50/80 dark:border-violet-400/50 dark:bg-violet-900/20'
          : 'border-zinc-200/90 bg-white/95 dark:border-white/[0.08] dark:bg-zinc-950/50',
      ]"
      @dragover.prevent="isDraggingFile = true"
      @dragleave.self="isDraggingFile = false"
      @drop.prevent="handleDrop"
    >
      <div v-if="isDraggingFile" class="mx-auto mb-2 max-w-3xl flex items-center justify-center gap-2 rounded-xl border border-dashed border-violet-400 py-2 text-sm font-medium text-violet-600 dark:border-violet-400/60 dark:text-violet-300">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/></svg>
        {{ t('chat.dropUploadRelease') }}
      </div>
      <div v-if="attachmentList.length" class="mx-auto mb-2 max-w-3xl flex flex-wrap gap-2">
        <div
          v-for="att in attachmentList"
          :key="att.file_uuid"
          class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors
            border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
        >
          <svg class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
          <span class="max-w-[120px] truncate">{{ att.original_filename || att.filename }}</span>
          <span
            :class="att.mode === 'rag'
              ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
              : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'"
          >{{
              att.mode === 'rag' ? t('chat.attachmentRag') : t('chat.attachmentInline')
            }}</span>
          <button
            @click="deleteAttachment(att.file_uuid)"
            class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400"
          >
            <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div v-if="uploadError" class="mx-auto mb-2 max-w-3xl rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 flex items-center gap-2">
        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/></svg>
        {{ uploadError }}
        <button
          type="button"
          @click="uploadError = ''"
          class="ml-auto text-red-400 hover:text-red-600"
          :aria-label="t('chat.dismissUploadError')"
        >
          ✕
        </button>
      </div>

      <div
        class="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-zinc-200/90 bg-white px-4 py-3 shadow-lg ring-1 ring-zinc-200/40 transition-colors duration-300 dark:border-white/[0.1] dark:bg-white/[0.05] dark:shadow-[0_20px_40px_-16px_rgba(0,0,0,0.55)] dark:ring-white/10 dark:backdrop-blur-md"
      >
        <label
          :class="[
            'flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-xl transition-all duration-200',
            uploading
              ? 'bg-violet-100 text-violet-400 dark:bg-violet-900/30 dark:text-violet-400'
              : 'text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:text-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-300',
          ]"
          :title="t('chat.attachFile')"
        >
          <input
            ref="fileInputEl"
            type="file"
            class="hidden"
            accept=".pdf,.docx,.txt,.md"
            :disabled="uploading"
            @change="handleFileUpload"
          />
          <svg v-if="!uploading" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
          <svg v-else class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
        </label>

        <textarea
          v-model="draft"
          rows="1"
          :placeholder="t('chat.placeholder')"
          class="max-h-32 flex-1 resize-none bg-transparent text-sm leading-relaxed text-zinc-950 outline-none transition-colors duration-200 placeholder:text-zinc-500 dark:text-zinc-100 dark:placeholder:text-zinc-500"
          @keydown.enter.exact.prevent="send"
          @input="autoResize"
          ref="textareaEl"
        />
        <button
          @click="send"
          :disabled="loading || uploading || (!draft.trim() && !attachmentList.length)"
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-zinc-950 text-white shadow-md transition-all duration-200 enabled:hover:scale-105 enabled:active:scale-95 disabled:bg-zinc-200 disabled:text-zinc-400 dark:bg-white dark:text-zinc-950 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { chatStream, newSessionId, deleteFileAsset, uploadFileAsset } from '../api/agent.js'
import DocumentFileIcon from './DocumentFileIcon.vue'
import { isDark as isDarkFn } from '../theme'
import { renderMarkdown } from '../utils/sanitizeHtml.js'

const { t } = useI18n()

/** Render assistant markdown once after streaming completes; hydrate history on demand. */
function assistantMessageHtml(msg) {
  if (msg?.renderedHtml) return msg.renderedHtml
  return renderMarkdown(msg?.content)
}

const props = defineProps({ sessionId: String, initialMessage: String })

const messages = ref([])
const draft = ref('')
const loading = ref(false)
const streamingMsg = ref(null)
const scrollEl = ref(null)
const textareaEl = ref(null)
const fileInputEl = ref(null)
const sessionId = ref(props.sessionId || newSessionId())
const dark = ref(typeof document !== 'undefined' && document.documentElement.classList.contains('dark'))

const attachmentList = ref([])
const uploading = ref(false)
const uploadError = ref('')
const isDraggingFile = ref(false)

const ACCEPTED_EXTS = new Set(['.pdf', '.docx', '.txt', '.md'])

/** Return true when a user bubble should remain visible without plain text content. */
function userMessageVisible(msg) {
  if (msg?.type === 'file') {
    return (msg.fileAttachments?.length ?? 0) > 0 || Boolean(msg.caption?.trim())
  }
  return Boolean(msg?.content?.trim())
}

/** Use compact attachment styling for user bubbles that include uploaded files. */
function userBubbleUsesAttachLayout(msg) {
  return msg?.role === 'user' && msg?.type === 'file' && (msg.fileAttachments?.length ?? 0) > 0
}

/** Build the API prompt when the user sends attachments without typing a message. */
function defaultAttachmentPrompt(attachments) {
  if (attachments.length > 1) return t('chat.fileReplyPromptMulti')
  return t('chat.fileReplyPrompt')
}

function resetTextarea() {
  nextTick(() => {
    if (!textareaEl.value) return
    textareaEl.value.style.height = 'auto'
  })
}

function clearComposer() {
  draft.value = ''
  attachmentList.value = []
  uploadError.value = ''
  resetTextarea()
}

function pushUserMessage(text, attachments) {
  const caption = text.trim()
  if (attachments.length) {
    messages.value.push({
      id: Date.now(),
      role: 'user',
      type: 'file',
      fileAttachments: attachments.map((item) => ({
        filename: item.original_filename || item.filename || t('chat.imageUntitled'),
        mode: item.mode,
      })),
      ...(caption ? { caption } : {}),
    })
    return
  }
  messages.value.push({ id: Date.now(), role: 'user', content: caption })
}

function handleDrop(e) {
  isDraggingFile.value = false
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  if (!ACCEPTED_EXTS.has(ext)) {
    uploadError.value = t('chat.uploadUnsupportedTypes', { ext })
    return
  }
  doUpload(file)
}

async function doUpload(file) {
  uploading.value = true
  uploadError.value = ''
  try {
    const uploaded = await uploadFileAsset(file)
    attachmentList.value = [...attachmentList.value, uploaded]
  } catch (err) {
    uploadError.value = err.message || t('chat.uploadFailed')
  } finally {
    uploading.value = false
  }
}

async function refreshAttachments() {
  // File references are persisted with chat message metadata, not a legacy attach API.
}

async function handleFileUpload(e) {
  const file = e.target.files?.[0]
  if (e.target) e.target.value = ''
  if (!file) return
  await doUpload(file)
}

async function deleteAttachment(fileUuid) {
  try {
    await deleteFileAsset(fileUuid)
    attachmentList.value = attachmentList.value.filter((item) => item.file_uuid !== fileUuid)
  } catch (err) {
    uploadError.value = err.message || t('chat.deleteFailed')
  }
}

function syncTheme() {
  dark.value = isDarkFn()
}

onMounted(() => {
  syncTheme()
  window.addEventListener('icore-theme-change', syncTheme)
  refreshAttachments()
})
onUnmounted(() => {
  window.removeEventListener('icore-theme-change', syncTheme)
})

if (props.initialMessage) {
  sendMessage(props.initialMessage)
}

async function send() {
  if (loading.value || uploading.value) return
  const text = draft.value.trim()
  const pendingAttachments = [...attachmentList.value]
  if (!text && !pendingAttachments.length) return

  pushUserMessage(text, pendingAttachments)
  clearComposer()

  const apiText = text || defaultAttachmentPrompt(pendingAttachments)
  await sendMessage(apiText, pendingAttachments)
}

async function sendMessage(msg, attachments = []) {
  loading.value = true
  await scrollBottom()

  const assistant = {
    id: Date.now() + 1,
    role: 'assistant',
    content: '',
    streaming: true,
    steps: [],
    stepsCollapsed: false,
  }
  messages.value.push(assistant)
  const replyIndex = messages.value.length - 1
  streamingMsg.value = messages.value[replyIndex]

  function commitAssistant(partial) {
    const cur = messages.value[replyIndex]
    const next = { ...cur, ...partial }
    messages.value[replyIndex] = next
    streamingMsg.value = next
  }

  try {
    for await (const evt of chatStream(msg, sessionId.value, '', {
      fileUuids: attachments.map((item) => item.file_uuid).filter(Boolean),
    })) {
      if (!evt) continue
      if (evt.kind === 'token') {
        const cur = messages.value[replyIndex]
        commitAssistant({
          content: (cur.content || '') + (evt.text || ''),
        })
      } else if (evt.kind === 'status') {
        const cur = messages.value[replyIndex]
        commitAssistant({
          steps: [
            ...cur.steps,
            {
              step: evt.step,
              tool: evt.tool,
              input_preview: evt.input_preview,
            },
          ],
        })
      }
      await scrollBottom()
    }
  } catch (e) {
    const err = e instanceof Error ? e.message : String(e)
    commitAssistant({
      content: t('chat.requestFailed', { msg: err }),
    })
  } finally {
    const cur = messages.value[replyIndex]
    commitAssistant({
      streaming: false,
      stepsCollapsed: true,
      renderedHtml: renderMarkdown(cur?.content || ''),
    })
    streamingMsg.value = null
    loading.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

function autoResize(e) {
  e.target.style.height = 'auto'
  e.target.style.height = e.target.scrollHeight + 'px'
}
</script>
