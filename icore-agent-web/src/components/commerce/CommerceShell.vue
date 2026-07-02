<template>
  <div class="min-h-screen bg-zinc-100 text-zinc-950 dark:bg-zinc-950 dark:text-zinc-100">
    <div class="flex min-h-screen">
      <CommerceSidebar class="hidden lg:flex" />

      <div class="flex min-w-0 flex-1 flex-col">
        <header class="border-b border-zinc-200 bg-white px-4 py-4 dark:border-white/10 dark:bg-zinc-950 sm:px-6">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div class="min-w-0">
              <p class="text-xs font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">{{ t('commerce.appLabel') }}</p>
              <h1 class="mt-1 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-white">{{ title }}</h1>
              <p class="mt-1 text-sm leading-6 text-zinc-500 dark:text-zinc-400">{{ subtitle }}</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <button
                type="button"
                class="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/5 dark:text-zinc-200"
                :aria-label="t('landing.nav.language')"
                @click="toggleLocale"
              >
                {{ currentLocale === 'zh-CN' ? t('common.localeShortEnglish') : t('common.localeShortChinese') }}
              </button>
              <button class="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-semibold text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/5 dark:text-zinc-200">
                {{ t('commerce.shell.sampleButton') }}
              </button>
              <button class="rounded-lg bg-zinc-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 dark:bg-white dark:text-zinc-950">
                {{ t('commerce.shell.uploadButton') }}
              </button>
            </div>
          </div>
        </header>

        <div class="grid min-h-0 flex-1 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px]">
          <main class="min-w-0 px-4 py-5 sm:px-6">
            <slot />
          </main>
          <aside class="border-t border-zinc-200 bg-white p-5 dark:border-white/10 dark:bg-zinc-950 xl:border-l xl:border-t-0">
            <div class="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]">
              <div class="flex items-center gap-2">
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white">
                  <Sparkles class="h-4 w-4" aria-hidden="true" />
                </div>
                <div>
                  <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ t('commerce.shell.assistantTitle') }}</p>
                  <p class="text-xs text-zinc-500 dark:text-zinc-400">{{ t('commerce.shell.assistantSubtitle') }}</p>
                </div>
              </div>
              <div class="mt-4 space-y-3 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                <p>{{ t('commerce.shell.assistantBody') }}</p>
                <div class="rounded-lg border border-zinc-200 bg-white p-3 text-xs leading-5 text-zinc-500 dark:border-white/10 dark:bg-zinc-950 dark:text-zinc-400">
                  {{ t('commerce.shell.assistantExample') }}
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { setLocalePreference } from '../../stores/preferences.js'
import CommerceSidebar from './CommerceSidebar.vue'

const { t, locale } = useI18n()
const currentLocale = computed(() => locale.value)

function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  setLocalePreference(locale.value)
}

defineProps({
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    required: true,
  },
})
</script>
