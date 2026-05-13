<template>
  <header class="sticky top-0 z-40 border-b border-black/5 bg-stone-50/80 backdrop-blur-xl backdrop-saturate-150 dark:border-white/10 dark:bg-zinc-950/75">
    <div class="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8 lg:py-4">
      <RouterLink to="/" class="flex min-w-0 items-center gap-3">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-zinc-950 text-white shadow-lg shadow-zinc-900/15 dark:bg-white dark:text-zinc-950">
          <span class="text-sm font-bold tracking-tight">iC</span>
        </div>
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-zinc-950 dark:text-white">{{ t('navbar.title') }}</p>
          <p class="truncate text-xs text-zinc-500 dark:text-zinc-400">{{ t('landing.nav.tagline') }}</p>
        </div>
      </RouterLink>

      <nav class="hidden items-center gap-6 lg:flex">
        <a
          v-for="item in navLinks"
          :key="item.href"
          :href="item.href"
          class="text-sm font-medium text-zinc-600 transition hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-white"
        >
          {{ item.label }}
        </a>
      </nav>

      <div class="hidden items-center gap-3 lg:flex">
        <button
          type="button"
          class="rounded-full border border-zinc-200 bg-white px-3.5 py-2 text-sm font-medium text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300 dark:hover:text-white"
          @click="toggleLocale"
        >
          {{ currentLocale === 'zh-CN' ? 'EN' : '中' }}
        </button>
        <RouterLink
          to="/#plans"
          class="rounded-full px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-200/70 hover:text-zinc-950 dark:text-zinc-300 dark:hover:bg-white/10 dark:hover:text-white"
        >
          {{ t('landing.nav.signIn') }}
        </RouterLink>
        <RouterLink
          to="/auth"
          class="rounded-full bg-zinc-950 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-zinc-900/15 transition hover:scale-[1.02] dark:bg-white dark:text-zinc-950"
        >
          {{ t('landing.nav.startFree') }}
        </RouterLink>
      </div>

      <div class="flex items-center gap-2 lg:hidden">
        <button
          type="button"
          class="inline-flex h-10 items-center justify-center rounded-2xl border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-700 shadow-sm dark:border-white/10 dark:bg-white/5 dark:text-zinc-200"
          @click="toggleLocale"
          :aria-label="t('landing.nav.language')"
        >
          {{ currentLocale === 'zh-CN' ? 'EN' : '中' }}
        </button>
        <RouterLink
          to="/auth"
          class="inline-flex h-10 items-center justify-center rounded-2xl bg-zinc-950 px-3.5 text-sm font-semibold text-white shadow-lg shadow-zinc-900/15 dark:bg-white dark:text-zinc-950"
        >
          {{ t('landing.nav.mobileCta') }}
        </RouterLink>
        <button
          type="button"
          class="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-zinc-200 bg-white text-zinc-700 dark:border-white/10 dark:bg-white/5 dark:text-zinc-200"
          @click="menuOpen = !menuOpen"
          :aria-label="t('landing.nav.menu')"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.9" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
      </div>
    </div>

    <div v-if="menuOpen" class="border-t border-black/5 px-4 py-4 dark:border-white/10 lg:hidden">
      <div class="rounded-[1.75rem] border border-black/5 bg-white/92 p-4 shadow-[0_24px_70px_-32px_rgba(24,24,27,0.4)] backdrop-blur-xl dark:border-white/10 dark:bg-zinc-900/92">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">{{ t('landing.nav.menuLabel') }}</p>
            <p class="mt-1 text-sm font-medium text-zinc-800 dark:text-zinc-200">{{ t('landing.nav.menuSubcopy') }}</p>
          </div>
          <button
            type="button"
            class="inline-flex h-9 w-9 items-center justify-center rounded-2xl border border-zinc-200 bg-white text-zinc-600 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300"
            @click="menuOpen = false"
            :aria-label="t('landing.nav.closeMenu')"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <nav class="grid grid-cols-2 gap-2.5">
        <a
          v-for="item in navLinks"
          :key="item.href"
          :href="item.href"
          class="rounded-2xl border border-zinc-200/80 bg-stone-50/90 px-3 py-3 text-sm font-medium text-zinc-700 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300"
          @click="menuOpen = false"
        >
          {{ item.label }}
        </a>
        </nav>
        <div class="mt-4 flex flex-col gap-2">
        <button
          type="button"
          class="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300"
          @click="toggleLocale"
        >
          {{ t('landing.nav.language') }}: {{ currentLocale === 'zh-CN' ? 'English' : '中文' }}
        </button>
          <div class="grid grid-cols-2 gap-2">
            <RouterLink
              to="/#plans"
              class="rounded-full border border-zinc-200 bg-white px-4 py-2.5 text-center text-sm font-medium text-zinc-700 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300"
              @click="menuOpen = false"
            >
              {{ t('landing.nav.signIn') }}
            </RouterLink>
            <RouterLink
              to="/auth"
              class="rounded-full bg-zinc-950 px-4 py-2.5 text-center text-sm font-semibold text-white dark:bg-white dark:text-zinc-950"
              @click="menuOpen = false"
            >
              {{ t('landing.nav.startFree') }}
            </RouterLink>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocalePreference } from '../../stores/preferences.js'

const { t, tm, locale } = useI18n()

const menuOpen = ref(false)
const currentLocale = computed(() => locale.value)
const navLinks = computed(() => {
  const items = tm('landing.nav.links')
  return Array.isArray(items) ? items : []
})

function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  setLocalePreference(locale.value)
}
</script>
