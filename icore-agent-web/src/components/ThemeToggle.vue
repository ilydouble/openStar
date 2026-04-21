<template>
  <button
    v-if="variant === 'icon'"
    type="button"
    @click="onClick"
    class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-zinc-200/90 bg-white text-zinc-700 shadow-sm transition-all duration-200 ease-out hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-950 dark:border-white/10 dark:bg-white/[0.06] dark:text-zinc-300 dark:shadow-none dark:hover:border-white/15 dark:hover:bg-white/[0.1] dark:hover:text-white"
    :title="dark ? t('theme.switchToLight') : t('theme.switchToDark')"
    :aria-label="dark ? t('theme.switchToLight') : t('theme.switchToDark')"
  >
    <svg
      v-if="dark"
      class="h-[18px] w-[18px]"
      fill="none"
      stroke="currentColor"
      stroke-width="1.75"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="12" r="4" />
      <path
        stroke-linecap="round"
        d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
      />
    </svg>
    <svg
      v-else
      class="h-[18px] w-[18px]"
      fill="none"
      stroke="currentColor"
      stroke-width="1.75"
      viewBox="0 0 24 24"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"
      />
    </svg>
  </button>

  <button
    v-else
    type="button"
    @click="onClick"
    class="flex w-full items-center justify-center gap-0 rounded-xl border border-zinc-200/90 bg-white/90 py-2.5 text-zinc-700 shadow-sm transition-all duration-200 ease-out hover:border-zinc-300 hover:bg-white hover:text-zinc-950 dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-zinc-300 dark:shadow-none dark:hover:border-white/15 dark:hover:bg-white/[0.08] dark:hover:text-white sm:justify-start sm:gap-3 sm:px-2"
    :title="dark ? t('theme.switchToLight') : t('theme.switchToDark')"
    :aria-label="dark ? t('theme.switchToLight') : t('theme.switchToDark')"
  >
    <span
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-200/90 bg-zinc-50 text-zinc-600 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-zinc-300"
    >
      <svg
        v-if="dark"
        class="h-4 w-4"
        fill="none"
        stroke="currentColor"
        stroke-width="1.75"
        viewBox="0 0 24 24"
      >
        <circle cx="12" cy="12" r="4" />
        <path
          stroke-linecap="round"
          d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
        />
      </svg>
      <svg
        v-else
        class="h-4 w-4"
        fill="none"
        stroke="currentColor"
        stroke-width="1.75"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"
        />
      </svg>
    </span>
    <span class="hidden min-w-0 truncate text-left text-xs font-medium sm:inline">
      {{ dark ? t('theme.switchToLight') : t('theme.switchToDark') }}
    </span>
  </button>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { isDark as isDarkFn, toggleTheme as toggleThemeFn } from '../theme'

defineProps({
  variant: {
    type: String,
    default: 'icon',
    validator: (v) => v === 'icon' || v === 'row',
  },
})

const { t } = useI18n()
const dark = ref(false)

function sync() {
  dark.value = isDarkFn()
}

function onClick() {
  toggleThemeFn()
  sync()
}

onMounted(() => {
  sync()
  window.addEventListener('icore-theme-change', sync)
})
onUnmounted(() => {
  window.removeEventListener('icore-theme-change', sync)
})
</script>
