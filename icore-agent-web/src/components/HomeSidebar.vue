<template>
  <aside
    class="flex h-full min-h-0 w-[4.5rem] shrink-0 flex-col border-r border-zinc-200/80 bg-white/90 backdrop-blur-xl transition-colors duration-300 ease-out dark:border-white/[0.08] dark:bg-zinc-950 sm:w-[13.5rem]"
  >
    <div class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto overflow-x-hidden px-2 pb-2 pt-4 sm:px-3">
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
        <span class="hidden truncate sm:inline">{{ t('home.sidebar.new') }}</span>
      </button>

      <RouterLink
        :to="{ name: 'home' }"
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
          <span class="hidden truncate sm:inline">{{ t('home.sidebar.home') }}</span>
        </a>
      </RouterLink>

      <RouterLink :to="{ name: 'chat' }" custom v-slot="{ href, navigate, isActive }">
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
          <span class="hidden truncate sm:inline">{{ t('home.sidebar.chat') }}</span>
        </a>
      </RouterLink>

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
        <span class="hidden truncate sm:inline">{{ t('home.sidebar.flow') }}</span>
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
          <span class="hidden truncate sm:inline">{{ t('home.sidebar.more') }}</span>
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
                {{ currentLocale === 'zh-CN' ? 'EN' : '中' }}
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
          </div>
        </Transition>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ThemeToggle from './ThemeToggle.vue'

const emit = defineEmits(['new', 'navigate'])

const { t, locale } = useI18n()

const moreOpen = ref(false)
const moreRootRef = ref(null)
const morePanelId = `sidebar-more-${Math.random().toString(36).slice(2, 9)}`

const currentLocale = computed(() => locale.value)

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
  localStorage.setItem('locale', locale.value)
  closeMore()
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
})
</script>
