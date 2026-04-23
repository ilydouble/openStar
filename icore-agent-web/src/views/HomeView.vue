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
                <SearchBar
                  ref="searchRefHome"
                  :placeholder="activeShortcut?.placeholder || ''"
                  :mode-pill="activeShortcutPill"
                  @submit="handleSubmit"
                  @file-selected="handleFileSelected"
                  @clear-mode="clearShortcut"
                />

                <!-- 附件列表（首页） -->
                <div v-if="attachmentList.length" class="mt-2 flex flex-wrap gap-2 justify-center">
                  <div
                    v-for="att in attachmentList"
                    :key="att.filename"
                    class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                           border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
                  >
                    <img
                      v-if="att.mode === 'image' && att.ref"
                      :src="imageUrl(att.ref)"
                      :alt="att.filename"
                      class="h-5 w-5 shrink-0 rounded object-cover"
                    />
                    <svg v-else class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                    <span class="max-w-[160px] truncate">{{ att.filename }}</span>
                    <span :class="att.mode === 'rag'
                      ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                      : att.mode === 'image'
                      ? 'rounded bg-fuchsia-100 px-1 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300'
                      : att.mode === 'data'
                      ? 'rounded bg-emerald-100 px-1 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                      : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'">
                      {{ att.mode === 'rag' ? 'RAG' : att.mode === 'image' ? '图片' : att.mode === 'data' ? '数据' : '内联' }}
                    </span>
                    <button @click="deleteAttachment(att.filename)" class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400">
                      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                  </div>
                  <div v-if="uploading" class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-900/20 dark:text-violet-300">
                    <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                    上传中...
                  </div>
                </div>
                <div v-else-if="uploading" class="mt-2 flex justify-center">
                  <div class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-900/20 dark:text-violet-300">
                    <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                    上传中...
                  </div>
                </div>
                <div v-if="uploadError" class="mt-2 mx-auto max-w-lg rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 flex items-center gap-2">
                  {{ uploadError }}
                  <button @click="uploadError = ''" class="ml-auto">✕</button>
                </div>
              </div>

              <div
                class="mt-6 flex max-w-3xl flex-wrap items-start justify-center gap-x-4 gap-y-6 sm:gap-x-6 sm:gap-y-8"
              >
                <button
                  v-for="item in shortcutItems"
                  :key="item.id"
                  type="button"
                  :disabled="loading"
                  :aria-pressed="activeShortcutId === item.id"
                  @click="toggleShortcut(item.id)"
                  class="group flex w-[4.5rem] flex-col items-center gap-2.5 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-100 disabled:opacity-50 dark:focus-visible:ring-violet-400/40 dark:focus-visible:ring-offset-zinc-950 sm:w-[5.25rem]"
                >
                  <span
                    :class="[
                      'flex h-12 w-12 items-center justify-center rounded-2xl border text-lg shadow-md ring-1 transition-all duration-300 ease-out group-hover:scale-110 group-hover:shadow-lg motion-reduce:transition-colors motion-reduce:group-hover:scale-100 sm:h-14 sm:w-14 sm:text-xl dark:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.5)] dark:group-hover:shadow-[0_16px_32px_-8px_rgba(0,0,0,0.55)]',
                      item.panel,
                      activeShortcutId === item.id
                        ? 'scale-110 ring-2 ring-violet-500 ring-offset-2 ring-offset-zinc-100 dark:ring-violet-400 dark:ring-offset-zinc-950'
                        : 'ring-black/5 group-hover:ring-black/10 dark:ring-white/10',
                    ]"
                  >
                    {{ item.emoji }}
                  </span>
                  <span
                    :class="[
                      'max-w-[5.5rem] text-center text-[11px] font-medium leading-tight transition-colors duration-200 sm:text-xs',
                      activeShortcutId === item.id
                        ? 'text-violet-600 dark:text-violet-300'
                        : 'text-zinc-600 group-hover:text-zinc-950 dark:text-zinc-400 dark:group-hover:text-zinc-200',
                    ]"
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
            <!-- 附件列表（对话模式） -->
            <div v-if="attachmentList.length || uploading || uploadError" class="mx-auto max-w-3xl mb-2">
              <div v-if="attachmentList.length || uploading" class="flex flex-wrap gap-2">
                <div
                  v-for="att in attachmentList"
                  :key="att.filename"
                  class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                         border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
                >
                  <img
                    v-if="att.mode === 'image' && att.ref"
                    :src="imageUrl(att.ref)"
                    :alt="att.filename"
                    class="h-5 w-5 shrink-0 rounded object-cover"
                  />
                  <svg v-else class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                  </svg>
                  <span class="max-w-[160px] truncate">{{ att.filename }}</span>
                  <span :class="att.mode === 'rag'
                    ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                    : att.mode === 'image'
                    ? 'rounded bg-fuchsia-100 px-1 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300'
                    : att.mode === 'data'
                    ? 'rounded bg-emerald-100 px-1 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'">
                    {{ att.mode === 'rag' ? 'RAG' : att.mode === 'image' ? '图片' : att.mode === 'data' ? '数据' : '内联' }}
                  </span>
                  <button @click="deleteAttachment(att.filename)" class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400">
                    <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/></svg>
                  </button>
                </div>
                <div v-if="uploading" class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-900/20 dark:text-violet-300">
                  <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                  上传中...
                </div>
              </div>
              <div v-if="uploadError" class="mt-1 rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 flex items-center gap-2">
                {{ uploadError }}
                <button @click="uploadError = ''" class="ml-auto">✕</button>
              </div>
            </div>
            <SearchBar
              ref="searchRefChat"
              :placeholder="activeShortcut?.placeholder || ''"
              :mode-pill="activeShortcutPill"
              @submit="handleSubmit"
              @file-selected="handleFileSelected"
              @clear-mode="clearShortcut"
            />
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
import {
  chatStream,
  newSessionId,
  attachFile,
  attachImage,
  attachData,
  imageUrl,
  listAttachments,
  removeAttachment,
} from '../api/agent.js'
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

// ── 附件状态 ──────────────────────────────────────────────────────────────
const attachmentList = ref([])
const uploading = ref(false)
const uploadError = ref('')

async function refreshAttachments() {
  try {
    attachmentList.value = await listAttachments(sessionId.value)
  } catch { /* 静默失败 */ }
}

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])
const DATA_EXTS = new Set(['.csv', '.xls', '.xlsx'])

function extOf(name) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

async function handleFileSelected(file) {
  uploading.value = true
  uploadError.value = ''
  try {
    const ext = extOf(file.name)
    if (IMAGE_EXTS.has(ext)) {
      await attachImage(file, sessionId.value)
    } else if (DATA_EXTS.has(ext)) {
      await attachData(file, sessionId.value)
    } else {
      await attachFile(file, sessionId.value)
    }
    await refreshAttachments()
  } catch (err) {
    uploadError.value = err.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

async function deleteAttachment(filename) {
  try {
    await removeAttachment(sessionId.value, filename)
    await refreshAttachments()
  } catch (err) {
    uploadError.value = err.message || '删除失败'
  }
}

provide(
  'hasChatMessages',
  computed(() => messages.value.length > 0),
)

const PILL_BY_ID = {
  research: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-900/40 dark:text-rose-200 dark:ring-rose-400/30',
  code:     'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-400/30',
  docs:     'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-900/40 dark:text-sky-200 dark:ring-sky-400/30',
  chat:     'bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-900/40 dark:text-violet-200 dark:ring-violet-400/30',
  image:    'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200 dark:bg-fuchsia-900/40 dark:text-fuchsia-200 dark:ring-fuchsia-400/30',
  data:     'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200 dark:ring-emerald-400/30',
}

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
      placeholder: row.placeholder || '',
      emoji: ui.emoji,
      panel: ui.panel,
    }
  })
})

const activeShortcutId = ref('')
const activeShortcut = computed(
  () => shortcutItems.value.find((it) => it.id === activeShortcutId.value) || null,
)
const activeShortcutPill = computed(() => {
  const it = activeShortcut.value
  if (!it) return null
  return {
    label: it.label,
    emoji: it.emoji,
    pillClass: PILL_BY_ID[it.id] || '',
  }
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

// 前端 shortcut id → 后端 agent_hint 映射。docs 按钮走 knowledge_agent。
const SHORTCUT_HINT = {
  research: 'research',
  code: 'code',
  docs: 'knowledge',
  chat: 'chat',
  image: 'image',
  data: 'data',
}

async function sendUserMessage(msg, agentHint = '') {
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
    steps: [],
    stepsCollapsed: false,
  }
  streamingMsg.value = reply
  messages.value.push(reply)

  try {
    for await (const evt of chatStream(text, sessionId.value, agentHint)) {
      if (!evt) continue
      if (evt.kind === 'token') {
        reply.content += evt.text || ''
      } else if (evt.kind === 'status') {
        reply.steps.push({
          step: evt.step,
          tool: evt.tool,
          input_preview: evt.input_preview,
        })
      }
      await scrollBottom()
    }
  } catch (e) {
    reply.content =
      locale.value === 'zh-CN' ? `请求失败：${e.message}` : `Request failed: ${e.message}`
  } finally {
    reply.streaming = false
    reply.stepsCollapsed = true
    streamingMsg.value = null
    loading.value = false
    await scrollBottom()
  }
}

function handleSubmit({ message }) {
  const hint = SHORTCUT_HINT[activeShortcutId.value] || ''
  sendUserMessage(message, hint)
}

function toggleShortcut(id) {
  activeShortcutId.value = activeShortcutId.value === id ? '' : id
  nextTick(() => {
    ;(messages.value.length ? searchRefChat.value : searchRefHome.value)?.focus?.()
  })
}

function clearShortcut() {
  activeShortcutId.value = ''
}

function onSidebarNew() {
  messages.value = []
  sessionId.value = newSessionId()
  loading.value = false
  streamingMsg.value = null
  attachmentList.value = []
  uploadError.value = ''
  activeShortcutId.value = ''
  nextTick(() => {
    ;(messages.value.length ? searchRefChat.value : searchRefHome.value)?.focus?.()
    if (scrollEl.value) scrollEl.value.scrollTop = 0
  })
}
</script>
