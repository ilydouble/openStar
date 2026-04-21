<template>
  <div
    class="flex h-screen min-h-0 bg-zinc-100 text-zinc-950 antialiased transition-colors duration-300 ease-out dark:bg-zinc-950 dark:text-zinc-100"
  >
    <HomeSidebar @new="onSidebarNew" />

    <div class="relative flex min-h-0 min-w-0 flex-1 flex-col">
      <div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div
          class="absolute inset-0 bg-zinc-100 transition-colors duration-300 ease-out dark:bg-zinc-950"
        />
        <div
          class="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(120,119,198,0.14),transparent)] opacity-60 transition-opacity duration-300 dark:bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(120,119,198,0.22),transparent)] dark:opacity-100"
        />
        <div
          class="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_100%_50%,rgba(59,130,246,0.06),transparent)] opacity-80 transition-opacity duration-300 dark:bg-[radial-gradient(ellipse_60%_40%_at_100%_50%,rgba(59,130,246,0.1),transparent)] dark:opacity-100"
        />
      </div>

      <header
        class="relative z-10 flex shrink-0 items-center justify-end gap-2 px-4 py-4 sm:px-8"
      >
        <button
          type="button"
          class="rounded-full px-4 py-2 text-sm font-medium text-zinc-700 transition-colors duration-300 hover:bg-zinc-200/80 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
        >
          {{ t('home.signIn') }}
        </button>
        <button
          type="button"
          class="rounded-full bg-zinc-950 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-zinc-900/20 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] dark:bg-white dark:text-zinc-950 dark:shadow-black/30"
        >
          {{ t('home.signUp') }}
        </button>
      </header>

      <main class="relative z-10 flex min-h-0 flex-1 flex-col">
        <div class="flex h-full min-h-0 flex-col">
          <div
            v-if="messages.length > 0"
            ref="scrollEl"
            class="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6"
          >
            <div class="mx-auto w-full max-w-3xl space-y-6">
              <div
                v-for="msg in messages"
                :key="msg.id"
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
          </div>

          <div
            v-else
            class="h-screen flex items-center justify-center px-4 sm:px-10"
          >
            <div class="flex w-full max-w-3xl flex-col items-center text-center">
              <div class="flex flex-col items-center gap-4 animate-home-hero-in">
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400"
                >
                  {{ t('navbar.title') }}
                </p>
                <h1
                  class="text-[1.65rem] font-semibold tracking-[-0.03em] text-zinc-950 sm:text-4xl md:text-[2.5rem] md:leading-[1.15] dark:text-white"
                >
                  {{ t('home.heroTitle') }}
                </h1>
                <p
                  class="max-w-md text-sm leading-relaxed text-zinc-600 sm:text-base dark:text-zinc-400"
                >
                  {{ t('home.subtitle') }}
                </p>
              </div>

              <div class="mt-6 w-full">
                <SearchBar ref="searchRefHome" @submit="handleSubmit" />
              </div>

              <div
                class="mt-6 flex max-w-3xl flex-wrap items-start justify-center gap-x-4 gap-y-6 sm:gap-x-6 sm:gap-y-8"
              >
                <button
                  v-for="item in shortcutItems"
                  :key="item.id"
                  type="button"
                  :disabled="loading"
                  @click="startWithPrompt(item.prompt)"
                  class="group flex w-[4.5rem] flex-col items-center gap-2.5 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-100 disabled:opacity-50 dark:focus-visible:ring-violet-400/40 dark:focus-visible:ring-offset-zinc-950 sm:w-[5.25rem]"
                >
                  <span
                    :class="[
                      'flex h-12 w-12 items-center justify-center rounded-2xl border text-lg shadow-md ring-1 ring-black/5 transition-all duration-300 ease-out group-hover:scale-110 group-hover:shadow-lg group-hover:ring-black/10 motion-reduce:transition-colors motion-reduce:group-hover:scale-100 sm:h-14 sm:w-14 sm:text-xl dark:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.5)] dark:ring-white/10 dark:group-hover:shadow-[0_16px_32px_-8px_rgba(0,0,0,0.55)]',
                      item.panel,
                    ]"
                  >
                    {{ item.emoji }}
                  </span>
                  <span
                    class="max-w-[5.5rem] text-center text-[11px] font-medium leading-tight text-zinc-600 transition-colors duration-200 group-hover:text-zinc-950 sm:text-xs dark:text-zinc-400 dark:group-hover:text-zinc-200"
                  >
                    {{ item.label }}
                  </span>
                </button>
              </div>
            </div>
          </div>

          <div
            v-if="messages.length > 0"
            class="relative z-30 shrink-0 border-t border-zinc-200 bg-zinc-100/85 p-4 backdrop-blur-md transition-all duration-500 ease-in-out dark:border-white/10 dark:bg-zinc-950/50 sm:px-8"
          >
            <SearchBar ref="searchRefChat" @submit="handleSubmit" />
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, provide } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import { chatStream, newSessionId } from '../api/agent.js'
import { isDark as isDarkFn } from '../theme'
import HomeSidebar from '../components/HomeSidebar.vue'
import SearchBar from '../components/SearchBar.vue'

const { t, locale, tm } = useI18n()

marked.setOptions({ breaks: true, gfm: true })

function renderMarkdown(text) {
  if (!text) return '&nbsp;'
  return marked.parse(text)
}

const UI_BY_ID = {
  research: {
    emoji: '\u{1F50D}',
    panel:
      'bg-gradient-to-br from-rose-100 to-rose-50 border-rose-200/80 dark:from-rose-600/40 dark:to-rose-950/55 dark:border-rose-400/20',
  },
  code: {
    emoji: '\u{26A1}',
    panel:
      'bg-gradient-to-br from-amber-100 to-amber-50 border-amber-200/80 dark:from-amber-500/35 dark:to-amber-950/55 dark:border-amber-400/20',
  },
  docs: {
    emoji: '\u{1F4C4}',
    panel:
      'bg-gradient-to-br from-sky-100 to-sky-50 border-sky-200/80 dark:from-sky-500/35 dark:to-sky-950/55 dark:border-sky-400/20',
  },
  chat: {
    emoji: '\u{1F4AC}',
    panel:
      'bg-gradient-to-br from-violet-100 to-violet-50 border-violet-200/80 dark:from-violet-500/40 dark:to-violet-950/55 dark:border-violet-400/20',
  },
  image: {
    emoji: '\u{2728}',
    panel:
      'bg-gradient-to-br from-fuchsia-100 to-fuchsia-50 border-fuchsia-200/80 dark:from-fuchsia-500/35 dark:to-fuchsia-950/55 dark:border-fuchsia-400/20',
  },
  data: {
    emoji: '\u{1F4CA}',
    panel:
      'bg-gradient-to-br from-emerald-100 to-emerald-50 border-emerald-200/80 dark:from-emerald-500/35 dark:to-emerald-950/55 dark:border-emerald-400/20',
  },
}

const messages = ref([])
const loading = ref(false)
const streamingMsg = ref(null)
const sessionId = ref(newSessionId())
const scrollEl = ref(null)
const searchRefHome = ref(null)
const searchRefChat = ref(null)
const dark = ref(typeof document !== 'undefined' && document.documentElement.classList.contains('dark'))

provide(
  'hasChatMessages',
  computed(() => messages.value.length > 0),
)

const shortcutItems = computed(() => {
  const raw = tm('home.shortcuts')
  if (!Array.isArray(raw)) return []
  return raw.map((row) => {
    const id = row.id
    const ui = UI_BY_ID[id] || {
      emoji: '\u2728',
      panel:
        'bg-gradient-to-br from-zinc-200 to-zinc-100 border-zinc-300/80 dark:from-zinc-800/80 dark:to-zinc-950/80 dark:border-white/10',
    }
    return {
      id,
      label: row.label,
      prompt: row.prompt,
      emoji: ui.emoji,
      panel: ui.panel,
    }
  })
})

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

async function scrollBottom() {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

async function sendUserMessage(msg) {
  if (!msg?.trim() || loading.value) return
  const text = msg.trim()

  messages.value.push({ id: `${Date.now()}-u`, role: 'user', content: text })
  loading.value = true
  await scrollBottom()

  const reply = {
    id: `${Date.now()}-a`,
    role: 'assistant',
    content: '',
    streaming: true,
  }
  streamingMsg.value = reply
  messages.value.push(reply)

  try {
    for await (const token of chatStream(text, sessionId.value)) {
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

function handleSubmit({ message }) {
  sendUserMessage(message)
}

function startWithPrompt(prompt) {
  sendUserMessage(prompt)
}

function onSidebarNew() {
  messages.value = []
  sessionId.value = newSessionId()
  loading.value = false
  streamingMsg.value = null
  nextTick(() => {
    ;(messages.value.length ? searchRefChat.value : searchRefHome.value)?.focus?.()
    if (scrollEl.value) scrollEl.value.scrollTop = 0
  })
}
</script>
