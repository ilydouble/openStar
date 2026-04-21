<template>
  <div
    class="flex h-full flex-col bg-zinc-100 transition-colors duration-300 ease-out dark:bg-zinc-950"
  >
    <div ref="scrollEl" class="flex-1 space-y-6 overflow-y-auto px-4 py-6 sm:px-6">
      <div v-for="msg in messages" :key="msg.id" :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
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

      <div v-if="loading && !streamingMsg" class="flex justify-start gap-3">
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
      class="border-t border-zinc-200/90 bg-white/95 px-4 py-3 backdrop-blur-xl transition-colors duration-300 dark:border-white/[0.08] dark:bg-zinc-950/50 sm:px-6"
    >
      <div
        class="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-zinc-200/90 bg-white px-4 py-3 shadow-lg ring-1 ring-zinc-200/40 transition-colors duration-300 dark:border-white/[0.1] dark:bg-white/[0.05] dark:shadow-[0_20px_40px_-16px_rgba(0,0,0,0.55)] dark:ring-white/10 dark:backdrop-blur-md"
      >
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
import { chatStream, newSessionId } from '../api/agent.js'
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
const sessionId = ref(props.sessionId || newSessionId())
const dark = ref(typeof document !== 'undefined' && document.documentElement.classList.contains('dark'))

function syncTheme() {
  dark.value = isDarkFn()
}

onMounted(() => {
  syncTheme()
  window.addEventListener('icore-theme-change', syncTheme)
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

  const reply = { id: Date.now() + 1, role: 'assistant', content: '', streaming: true }
  streamingMsg.value = reply
  messages.value.push(reply)

  try {
    for await (const token of chatStream(msg, sessionId.value)) {
      reply.content += token
      await scrollBottom()
    }
  } catch (e) {
    reply.content =
      locale.value === 'zh-CN' ? `请求失败：${e.message}` : `Request failed: ${e.message}`
  } finally {
    reply.streaming = false
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
