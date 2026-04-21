<template>
  <div
    :class="[
      'flex flex-col gap-2 transition-colors duration-300',
      floating
        ? 'rounded-2xl border border-zinc-200/90 bg-white/95 p-2 shadow-xl shadow-zinc-900/10 backdrop-blur-xl dark:border-white/[0.1] dark:bg-zinc-900/90 dark:shadow-black/40'
        : 'border-t border-zinc-200/80 bg-zinc-50/90 px-2 py-3 dark:border-white/[0.08] dark:bg-zinc-950/50 sm:px-3',
    ]"
  >
    <button
      type="button"
      @click="toggleLocale"
      class="flex w-full items-center justify-center gap-0 rounded-xl border border-zinc-200/90 bg-white/90 py-2.5 text-zinc-700 shadow-sm transition-all duration-200 ease-out hover:border-zinc-300 hover:bg-white hover:text-zinc-950 dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-zinc-300 dark:shadow-none dark:hover:border-white/15 dark:hover:bg-white/[0.08] dark:hover:text-white sm:justify-start sm:gap-3 sm:px-2"
      :title="currentLocale === 'zh-CN' ? 'Switch to English' : '切换中文'"
    >
      <span
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-200/90 bg-zinc-50 text-[11px] font-semibold text-zinc-700 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-zinc-200"
      >
        {{ currentLocale === 'zh-CN' ? 'EN' : '中' }}
      </span>
      <span class="hidden min-w-0 truncate text-left text-xs font-medium sm:inline">
        {{ t('home.sidebar.language') }}
      </span>
    </button>

    <ThemeToggle variant="row" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ThemeToggle from './ThemeToggle.vue'

defineProps({
  floating: { type: Boolean, default: false },
})

const { t, locale } = useI18n()

const currentLocale = computed(() => locale.value)

function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  localStorage.setItem('locale', locale.value)
}
</script>
