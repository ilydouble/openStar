<template>
  <header
    class="fixed top-0 inset-x-0 z-50 flex h-14 items-center border-b border-zinc-200/90 bg-white/95 px-5 backdrop-blur-2xl backdrop-saturate-150 transition-colors duration-300 ease-out dark:border-white/[0.08] dark:bg-zinc-950/50 sm:px-6"
  >
    <div class="flex min-w-0 items-center gap-2.5">
      <div
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-zinc-950 text-white shadow-md ring-1 ring-zinc-950/20 transition-colors duration-300 dark:bg-gradient-to-br dark:from-zinc-100 dark:to-zinc-300 dark:text-zinc-950 dark:shadow-lg dark:shadow-black/40 dark:ring-white/10"
      >
        <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
          <path
            d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 3a1 1 0 110 2 1 1 0 010-2zm-1 4h2v5H9V9z"
          />
        </svg>
      </div>
      <span class="truncate text-sm font-semibold tracking-tight text-zinc-950 transition-colors duration-300 dark:text-white">
        {{ t('navbar.title') }}
      </span>
    </div>
  </header>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
