<template>
  <aside
    class="flex h-full min-h-0 w-[min(19rem,calc(100vw-2.5rem))] shrink-0 flex-col border-r border-zinc-200/80 bg-white/90 backdrop-blur-xl transition-colors duration-300 ease-out dark:border-white/[0.08] dark:bg-zinc-950 lg:w-[13.5rem]"
  >
    <div class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto overflow-x-hidden px-3 pb-2 pt-4 lg:px-3">
      <button
        type="button"
        @click="onNew"
        class="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm font-medium text-zinc-700 transition-colors duration-200 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
      >
        <span
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-200/90 bg-zinc-50 text-zinc-600 transition-colors duration-200 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-400"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M12 5v14M5 12h14" />
          </svg>
        </span>
        <span class="min-w-0 truncate">{{ t('home.sidebar.new') }}</span>
      </button>

      <RouterLink
        :to="{ name: 'workspace' }"
        custom
        v-slot="{ href, navigate, isExactActive }"
      >
        <a
          :href="href"
          class="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm font-medium transition-colors duration-200"
          :class="navItemClass(isExactActive)"
          @click.prevent="
            () => {
              navigate()
              emitNavigate()
            }
          "
        >
          <span :class="iconWrapClass(isExactActive)">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-5v-6H10v6H5a1 1 0 01-1-1v-9.5z"
              />
            </svg>
          </span>
          <span class="min-w-0 truncate">{{ t('home.sidebar.home') }}</span>
        </a>
      </RouterLink>

      <RouterLink
        :to="chatNavTo"
        custom
        v-slot="{ href, navigate, isActive }"
      >
        <a
          :href="href"
          class="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm font-medium transition-colors duration-200"
          :class="navItemClass(isActive)"
          @click.prevent="
            () => {
              navigate()
              emitNavigate()
            }
          "
        >
          <span :class="iconWrapClass(isActive)">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M8 10h.01M12 10h.01M16 10h.01M4 18l4-4h10a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12z"
              />
            </svg>
          </span>
          <span class="min-w-0 truncate">{{ t('home.sidebar.chat') }}</span>
        </a>
      </RouterLink>

      <RouterLink
        :to="{ name: 'account' }"
        custom
        v-slot="{ href, navigate, isActive }"
      >
        <a
          :href="href"
          class="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm font-medium transition-colors duration-200"
          :class="navItemClass(isActive)"
          @click.prevent="
            () => {
              navigate()
              emitNavigate()
            }
          "
        >
          <span :class="iconWrapClass(isActive)">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6.75a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.5 19.5a7.5 7.5 0 0115 0" />
            </svg>
          </span>
          <span class="min-w-0 truncate">{{ t('home.accountCenter') }}</span>
        </a>
      </RouterLink>

      <div class="mt-3">
        <p class="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
          {{ t('home.recent.title') }}
        </p>
        <div class="mt-2 px-2">
          <label class="sr-only" for="sidebar-session-search">{{ t('home.sidebar.searchPlaceholder') }}</label>
          <div class="relative">
            <svg
              class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400 dark:text-zinc-500"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M10.5 18a7.5 7.5 0 100-15 7.5 7.5 0 000 15z" />
            </svg>
            <input
              id="sidebar-session-search"
              v-model="searchInput"
              type="search"
              autocomplete="off"
              :placeholder="t('home.sidebar.searchPlaceholder')"
              class="w-full rounded-lg border border-zinc-200/90 bg-zinc-50/90 py-1.5 pl-8 pr-7 text-xs text-zinc-800 placeholder:text-zinc-400 focus:border-violet-300 focus:outline-none focus:ring-2 focus:ring-violet-200/70 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-100 dark:placeholder:text-zinc-500 dark:focus:border-violet-400/40 dark:focus:ring-violet-500/20"
            />
            <button
              v-if="searchInput"
              type="button"
              class="absolute right-1.5 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-zinc-400 hover:text-zinc-600 dark:text-zinc-500 dark:hover:text-zinc-300"
              :aria-label="t('home.sidebar.clearSearch')"
              @click="clearSearch"
            >
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
        </div>

        <div v-if="isSearching" class="mt-2 space-y-1.5">
          <p v-if="searchLoading" class="px-2 text-xs text-zinc-400 dark:text-zinc-500">
            {{ t('home.sidebar.searchLoading') }}
          </p>
          <template v-else-if="searchResults.length">
            <RouterLink
              v-for="item in searchResults"
              :key="item.sessionId"
              :to="{ name: 'workspace-session', params: { sessionId: item.sessionId } }"
              class="block rounded-xl border border-zinc-200/80 bg-zinc-50/80 px-3 py-2 transition hover:border-zinc-300 hover:bg-white dark:border-white/[0.08] dark:bg-white/[0.03] dark:hover:border-white/12 dark:hover:bg-white/[0.06]"
              @click="emitNavigate"
            >
              <p class="truncate text-xs font-semibold text-zinc-700 dark:text-zinc-200">
                {{ item.title }}
              </p>
              <p
                v-if="item.snippet"
                class="search-snippet mt-1 line-clamp-3 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400"
                v-html="item.snippet"
              />
            </RouterLink>
          </template>
          <p v-else class="px-2 text-xs text-zinc-400 dark:text-zinc-500">
            {{ t('home.sidebar.searchEmpty') }}
          </p>
        </div>

        <div v-else-if="recentSessions.length" class="mt-2 space-y-1.5">
          <RouterLink
            v-for="item in visibleRecentSessions"
            :key="item.sessionId"
            :to="{ name: 'workspace-session', params: { sessionId: item.sessionId } }"
            class="block rounded-xl border border-zinc-200/80 bg-zinc-50/80 px-3 py-2 transition hover:border-zinc-300 hover:bg-white dark:border-white/[0.08] dark:bg-white/[0.03] dark:hover:border-white/12 dark:hover:bg-white/[0.06]"
            @click="emitNavigate"
          >
            <p class="truncate text-xs font-semibold text-zinc-700 dark:text-zinc-200">
              {{ item.title }}
            </p>
            <p class="mt-1 truncate text-[11px] text-zinc-500 dark:text-zinc-400">
              {{ item.subtitle }}
            </p>
          </RouterLink>
          <button
            v-if="canToggleSessionsList"
            type="button"
            class="w-full rounded-lg px-2 py-1.5 text-left text-[11px] font-medium text-violet-600 transition hover:bg-violet-50 hover:text-violet-700 dark:text-violet-300 dark:hover:bg-violet-500/10 dark:hover:text-violet-200"
            @click="sessionsExpanded = !sessionsExpanded"
          >
            {{ sessionsExpanded ? t('home.recent.showLess') : t('home.recent.showMore') }}
          </button>
        </div>
        <p v-else class="mt-2 px-2 text-xs text-zinc-400 dark:text-zinc-500">
          {{ t('home.recent.empty') }}
        </p>
      </div>

      <div class="mt-4">
        <p class="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
          {{ t('home.projects.title') }}
        </p>
        <div v-if="recentProjects.length" class="mt-2 space-y-1.5">
          <div
            v-for="project in recentProjects"
            :key="project.id"
            class="rounded-xl border border-zinc-200/80 bg-zinc-50/80 px-3 py-2 dark:border-white/[0.08] dark:bg-white/[0.03]"
          >
            <p class="truncate text-xs font-semibold text-zinc-700 dark:text-zinc-200">
              {{ project.title }}
            </p>
            <p class="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
              {{ project.sessions }} {{ t('home.projects.sessions') }} · {{ project.assets }} {{ t('home.projects.assets') }}
            </p>
          </div>
        </div>
        <p v-else class="mt-2 px-2 text-xs text-zinc-400 dark:text-zinc-500">
          {{ t('home.projects.empty') }}
        </p>
      </div>

      <div
        role="presentation"
        class="flex cursor-not-allowed select-none items-center gap-3 rounded-xl px-2 py-2 text-sm font-medium text-zinc-400 opacity-50 pointer-events-none dark:text-zinc-600"
        :title="t('home.sidebar.flowSoon')"
      >
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-200/60 bg-zinc-50/80 text-zinc-400 dark:border-white/[0.06] dark:bg-white/[0.02] dark:text-zinc-600">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </span>
        <span class="min-w-0 truncate">{{ t('home.sidebar.flow') }}</span>
      </div>

      <div ref="moreRootRef" class="relative mt-auto shrink-0 pt-1">
        <button
          type="button"
          :aria-expanded="moreOpen"
          :aria-controls="morePanelId"
          :aria-label="t('home.sidebar.moreMenuLabel')"
          class="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm font-medium transition-colors duration-200"
          :class="navItemClass(moreOpen)"
          @click.stop="toggleMore"
        >
          <span :class="iconWrapClass(moreOpen)">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <circle cx="5" cy="12" r="1.5" fill="currentColor" />
              <circle cx="12" cy="12" r="1.5" fill="currentColor" />
              <circle cx="19" cy="12" r="1.5" fill="currentColor" />
            </svg>
          </span>
          <span class="min-w-0 truncate">{{ t('home.sidebar.more') }}</span>
        </button>

        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="-translate-y-1 opacity-0 scale-[0.98]"
          enter-to-class="translate-y-0 opacity-100 scale-100"
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
        >
          <div
            v-show="moreOpen"
            :id="morePanelId"
            role="menu"
            class="absolute bottom-full left-0 right-0 z-[80] mb-1 origin-bottom rounded-xl border border-zinc-200/90 bg-white/98 py-1 shadow-lg shadow-zinc-900/10 ring-1 ring-black/[0.04] backdrop-blur-md dark:border-white/[0.08] dark:bg-zinc-900/98 dark:shadow-black/40 dark:ring-white/[0.06]"
          >
            <button
              type="button"
              role="menuitem"
              class="flex w-full items-center gap-2.5 px-2.5 py-2 text-left text-xs font-medium text-zinc-800 transition-colors hover:bg-zinc-100 dark:text-zinc-100 dark:hover:bg-white/[0.06]"
              @click="toggleLocale"
            >
              <span
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-zinc-200/90 bg-zinc-50 text-[10px] font-semibold text-zinc-700 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-zinc-200"
              >
                {{
                  currentLocale === 'zh-CN' ? t('common.localeShortEnglish') : t('common.localeShortChinese')
                }}
              </span>
              <span class="min-w-0 flex-1 truncate">{{ t('home.sidebar.language') }}</span>
            </button>

            <div
              role="menuitem"
              class="flex items-center justify-between gap-2 px-2.5 py-2 text-xs font-medium text-zinc-800 dark:text-zinc-100"
            >
              <span class="shrink-0 text-zinc-600 dark:text-zinc-400">{{ t('home.sidebar.themeLabel') }}</span>
              <ThemeToggle variant="icon" />
            </div>
            <!-- 分隔线 -->
            <div class="mx-2.5 my-1 h-px bg-zinc-200/80 dark:bg-white/[0.08]" role="separator" />
            <!-- 退出登录 -->
            <button
              type="button"
              role="menuitem"
              class="flex w-full items-center gap-2.5 px-2.5 py-2 text-left text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
              @click="handleSignOut"
            >
              <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M18 15l3-3m0 0l-3-3m3 3H9" />
              </svg>
              <span class="min-w-0 flex-1 truncate">{{ t('home.signOut') }}</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocalePreference } from '../stores/preferences.js'
import { clearSession } from '../auth/session.js'
import ThemeToggle from './ThemeToggle.vue'

const emit = defineEmits(['new', 'navigate', 'search'])

const props = defineProps({
  currentSessionId: {
    type: String,
    default: '',
  },
  recentSessions: {
    type: Array,
    default: () => [],
  },
  recentProjects: {
    type: Array,
    default: () => [],
  },
  searchResults: {
    type: Array,
    default: () => [],
  },
  searchLoading: {
    type: Boolean,
    default: false,
  },
})

const { t, locale } = useI18n()
const router = useRouter()

const SESSIONS_PREVIEW_COUNT = 3
const searchInput = ref('')
const sessionsExpanded = ref(false)
const searchDebounceMs = 300
let searchTimer = null

const isSearching = computed(() => searchInput.value.trim().length > 0)

const visibleRecentSessions = computed(() => {
  if (sessionsExpanded.value) return props.recentSessions
  return props.recentSessions.slice(0, SESSIONS_PREVIEW_COUNT)
})

const canToggleSessionsList = computed(
  () => props.recentSessions.length > SESSIONS_PREVIEW_COUNT,
)

/** Debounce sidebar search input before requesting results from the parent. */
watch(searchInput, (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    emit('search', value.trim())
  }, searchDebounceMs)
})

function clearSearch() {
  searchInput.value = ''
  emit('search', '')
}

const moreOpen = ref(false)
const moreRootRef = ref(null)
const morePanelId = `sidebar-more-${Math.random().toString(36).slice(2, 9)}`

const currentLocale = computed(() => locale.value)

/** Chat nav targets the session route so it does not share active state with Home. */
const chatNavTo = computed(() => {
  const sessionId =
    props.currentSessionId || props.recentSessions[0]?.sessionId || ''
  return {
    name: 'workspace-session',
    params: { sessionId },
  }
})

function navItemClass(active) {
  return active
    ? 'bg-zinc-200/90 text-zinc-950 shadow-sm ring-1 ring-zinc-300/50 dark:bg-white/[0.1] dark:text-white dark:shadow-[0_0_0_1px_rgba(255,255,255,0.08)] dark:ring-white/10'
    : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-500 dark:hover:bg-white/[0.05] dark:hover:text-zinc-200'
}

function iconWrapClass(active) {
  return [
    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-colors duration-200',
    active
      ? 'border-zinc-300/90 bg-white text-zinc-950 dark:border-white/15 dark:bg-white/[0.1] dark:text-white'
      : 'border-zinc-200/90 bg-zinc-50 text-zinc-600 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-400',
  ]
}

function emitNavigate() {
  emit('navigate')
}

function onNew() {
  emit('new')
  emitNavigate()
}

function toggleMore() {
  moreOpen.value = !moreOpen.value
}

function closeMore() {
  moreOpen.value = false
}

function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  setLocalePreference(locale.value)
  closeMore()
}

/** 清除 session 并跳转到登录页 */
function handleSignOut() {
  clearSession()
  closeMore()
  router.push({ name: 'auth' })
}

function onDocClick(e) {
  if (moreRootRef.value && !moreRootRef.value.contains(e.target)) {
    closeMore()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<style scoped>
.search-snippet :deep(mark) {
  border-radius: 0.2rem;
  background-color: rgb(254 240 138 / 0.85);
  color: rgb(24 24 27);
  padding: 0 0.12rem;
  font-weight: 600;
}

:global(.dark) .search-snippet :deep(mark) {
  background-color: rgb(251 191 36 / 0.28);
  color: rgb(254 243 199);
}
</style>
