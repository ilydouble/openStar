<template>
  <div
    class="flex h-full flex-col bg-zinc-100 transition-colors duration-300 ease-out dark:bg-zinc-950"
  >
    <div ref="scrollEl" class="flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-6">
      <div
        v-for="msg in messages"
        :key="msg.id"
        v-show="msg.role === 'user' || msg.content || (msg.steps && msg.steps.length)"
        :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
      >
        <div
          v-if="msg.role === 'user'"
          class="max-w-[70%] rounded-2xl rounded-tr-sm bg-zinc-900 px-4 py-3 text-sm leading-relaxed text-white shadow-md ring-1 ring-zinc-900/20 transition-colors duration-300 dark:bg-zinc-800 dark:shadow-lg dark:shadow-black/20 dark:ring-white/10"
        >
          {{ msg.content }}
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
              v-html="renderMarkdown(msg.content)"
            />
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
      <!-- 拖拽提示 -->
      <div v-if="isDraggingFile" class="mx-auto mb-2 max-w-3xl flex items-center justify-center gap-2 rounded-xl border border-dashed border-violet-400 py-2 text-sm font-medium text-violet-600 dark:border-violet-400/60 dark:text-violet-300">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/></svg>
        松开鼠标上传文件（PDF / DOCX / TXT / MD）
      </div>
      <!-- 附件列表 -->
      <div v-if="attachmentList.length" class="mx-auto mb-2 max-w-3xl flex flex-wrap gap-2">
        <div
          v-for="att in attachmentList"
          :key="att.filename"
          class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors
            border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
        >
          <svg class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
          <span class="max-w-[120px] truncate">{{ att.filename }}</span>
          <span
            :class="att.mode === 'rag'
              ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
              : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'"
          >{{ att.mode === 'rag' ? 'RAG' : '内联' }}</span>
          <button
            @click="deleteAttachment(att.filename)"
            class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400"
          >
            <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- 上传错误提示 -->
      <div v-if="uploadError" class="mx-auto mb-2 max-w-3xl rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 flex items-center gap-2">
        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/></svg>
        {{ uploadError }}
        <button @click="uploadError = ''" class="ml-auto text-red-400 hover:text-red-600">✕</button>
      </div>

      <div
        class="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-zinc-200/90 bg-white px-4 py-3 shadow-lg ring-1 ring-zinc-200/40 transition-colors duration-300 dark:border-white/[0.1] dark:bg-white/[0.05] dark:shadow-[0_20px_40px_-16px_rgba(0,0,0,0.55)] dark:ring-white/10 dark:backdrop-blur-md"
      >
        <!-- 文件上传按钮 -->
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
          :disabled="loading || !draft.trim()"
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
import { marked } from 'marked'
import { chatStream, newSessionId, attachFile, listAttachments, removeAttachment } from '../api/agent.js'
import { isDark as isDarkFn } from '../theme'

const { t, locale } = useI18n()

marked.setOptions({ breaks: true, gfm: true })

function renderMarkdown(text) {
  if (!text) return '&nbsp;'
  return marked.parse(text)
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

// ── 附件状态 ──────────────────────────────────────────────────────────────
const attachmentList = ref([])
const uploading = ref(false)
const uploadError = ref('')
const isDraggingFile = ref(false)

const ACCEPTED_EXTS = new Set(['.pdf', '.docx', '.txt', '.md'])

function handleDrop(e) {
  isDraggingFile.value = false
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  if (!ACCEPTED_EXTS.has(ext)) {
    uploadError.value = `不支持的文件类型：${ext}，请上传 PDF / DOCX / TXT / MD`
    return
  }
  doUpload(file)
}

async function doUpload(file) {
  uploading.value = true
  uploadError.value = ''
  try {
    await attachFile(file, sessionId.value)
    await refreshAttachments()
  } catch (err) {
    uploadError.value = err.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

async function refreshAttachments() {
  try {
    attachmentList.value = await listAttachments(sessionId.value)
  } catch {
    // 静默失败，不影响对话
  }
}

async function handleFileUpload(e) {
  const file = e.target.files?.[0]
  if (e.target) e.target.value = '' // 允许重复上传同名文件
  if (!file) return
  await doUpload(file)
}

async function deleteAttachment(filename) {
  try {
    await removeAttachment(sessionId.value, filename)
    await refreshAttachments()
  } catch (err) {
    uploadError.value = err.message || '删除失败'
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
  const msg = draft.value.trim()
  if (!msg || loading.value) return
  draft.value = ''
  await sendMessage(msg)
}

async function sendMessage(msg) {
  messages.value.push({ id: Date.now(), role: 'user', content: msg })
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
  // push sonrası index sabit: iç nesneyi mutasyona değil replace ile güncelliyoruz
  // (push sonrası elde tutulan referans / proxy farkı yüzünden ekrana tek seferde yansıma
  // sorununu giderir).
  const replyIndex = messages.value.length - 1
  streamingMsg.value = messages.value[replyIndex]

  function commitAssistant(partial) {
    const cur = messages.value[replyIndex]
    const next = { ...cur, ...partial }
    messages.value[replyIndex] = next
    streamingMsg.value = next
  }

  try {
    for await (const evt of chatStream(msg, sessionId.value)) {
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
      content:
        locale.value === 'zh-CN' ? `请求失败：${err}` : `Request failed: ${err}`,
    })
  } finally {
    commitAssistant({
      streaming: false,
      stepsCollapsed: true,
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
