<template>
  <section id="results" class="relative overflow-hidden px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
    <div class="mx-auto max-w-7xl">
      <div data-reveal class="reveal-on-scroll text-center">
        <p class="inline-flex rounded-full border border-emerald-200 bg-emerald-50/90 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-700 shadow-sm dark:border-emerald-300/20 dark:bg-emerald-300/10 dark:text-emerald-200">
          {{ t('landing.results.eyebrow') }}
        </p>
        <h2 class="font-landing-display mt-5 text-4xl font-semibold tracking-[-0.04em] text-zinc-950 dark:text-white sm:text-5xl">
          {{ t('landing.results.title') }}
        </h2>
        <p class="mx-auto mt-5 max-w-2xl text-lg leading-8 text-zinc-600 dark:text-zinc-300">
          {{ t('landing.results.subtitle') }}
        </p>
      </div>

      <div data-reveal class="reveal-on-scroll mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <article
          v-for="(item, index) in resultItems"
          :key="index"
          class="group rounded-[2rem] border border-zinc-200/80 bg-white/85 p-8 shadow-sm transition-all duration-300 hover:scale-[1.02] hover:shadow-lg dark:border-white/10 dark:bg-white/[0.04] dark:hover:shadow-xl"
        >
          <div class="flex items-start justify-between">
            <div
              class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-3xl"
              :class="item.bgClass"
            >
              {{ item.emoji }}
            </div>
            <span
              class="rounded-full px-3 py-1 text-xs font-semibold"
              :class="item.badgeClass"
            >
              {{ item.badge }}
            </span>
          </div>
          <h3 class="mt-6 text-3xl font-bold text-zinc-950 dark:text-white">
            {{ item.value }}
          </h3>
          <p class="mt-2 text-sm font-semibold text-zinc-700 dark:text-zinc-200">
            {{ item.label }}
          </p>
          <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
            {{ item.body }}
          </p>
        </article>
      </div>

      <div data-reveal class="reveal-on-scroll mt-12 rounded-[2rem] border border-zinc-200/80 bg-gradient-to-br from-violet-50/80 to-white/80 p-8 shadow-sm dark:border-white/10 dark:from-violet-950/20 dark:to-zinc-900/40 sm:p-12">
        <div class="grid gap-8 lg:grid-cols-2 lg:items-center">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.22em] text-violet-600 dark:text-violet-300">
              {{ t('landing.results.impact.eyebrow') }}
            </p>
            <h3 class="mt-4 text-2xl font-semibold text-zinc-950 dark:text-white sm:text-3xl">
              {{ t('landing.results.impact.title') }}
            </h3>
            <p class="mt-4 text-base leading-7 text-zinc-600 dark:text-zinc-300">
              {{ t('landing.results.impact.body') }}
            </p>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <div
              v-for="(metric, index) in impactMetrics"
              :key="index"
              class="rounded-2xl border border-zinc-200/80 bg-white/90 p-5 dark:border-white/10 dark:bg-zinc-900/60"
            >
              <p class="text-2xl font-bold text-violet-600 dark:text-violet-300">
                {{ metric.value }}
              </p>
              <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
                {{ metric.label }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, tm } = useI18n()

const resultItems = computed(() => {
  const raw = tm('landing.results.items')
  return Array.isArray(raw) ? raw : []
})

const impactMetrics = computed(() => {
  const raw = tm('landing.results.impact.metrics')
  return Array.isArray(raw) ? raw : []
})
</script>
