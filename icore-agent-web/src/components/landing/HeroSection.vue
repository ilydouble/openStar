<template>
  <section class="relative overflow-hidden px-4 pb-10 pt-10 sm:px-6 lg:px-8 lg:pb-18 lg:pt-24">
    <div class="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)] lg:items-center">
      <div data-reveal class="reveal-on-scroll">
        <p class="inline-flex rounded-full border border-amber-200 bg-amber-50/90 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-amber-700 shadow-sm dark:border-amber-300/20 dark:bg-amber-300/10 dark:text-amber-200">
          {{ t('landing.hero.eyebrow') }}
        </p>
        <h1 class="font-landing-display mt-5 max-w-4xl text-[3.35rem] leading-[0.94] tracking-[-0.06em] text-zinc-950 dark:text-white sm:text-6xl sm:leading-[0.96] lg:mt-6 lg:text-[4.75rem] lg:leading-[0.98]">
          {{ t('landing.hero.title') }}
        </h1>
        <p class="mt-5 max-w-2xl text-[15px] leading-7 text-zinc-600 dark:text-zinc-300 sm:text-lg sm:leading-8">
          {{ t('landing.hero.subtitle') }}
        </p>

        <div class="mt-7 flex flex-col gap-3 sm:flex-row">
          <RouterLink
            to="/auth"
            class="inline-flex min-h-12 items-center justify-center rounded-full bg-zinc-950 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-zinc-900/15 transition hover:scale-[1.02] dark:bg-white dark:text-zinc-950"
          >
            {{ t('landing.hero.primaryCta') }}
          </RouterLink>
          <a
            href="#plans"
            class="inline-flex min-h-12 items-center justify-center rounded-full border border-zinc-200 bg-white px-6 py-3 text-sm font-semibold text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/5 dark:text-zinc-200 dark:hover:text-white"
          >
            {{ t('landing.hero.secondaryCta') }}
          </a>
        </div>

        <div class="hide-scrollbar mt-7 flex snap-x snap-mandatory items-center gap-3 overflow-x-auto pb-1 text-sm text-zinc-500 dark:text-zinc-400 sm:flex-wrap sm:overflow-visible sm:pb-0">
          <span
            v-for="item in trustPills"
            :key="item"
            class="snap-start whitespace-nowrap rounded-full border border-zinc-200 bg-white/85 px-3 py-1.5 font-medium shadow-sm dark:border-white/10 dark:bg-white/[0.04]"
          >
            {{ item }}
          </span>
        </div>

        <div class="mt-8 grid gap-3 sm:grid-cols-3">
          <div
            v-for="item in proofItems"
            :key="item.title"
            class="rounded-3xl border border-black/5 bg-white/85 p-4 shadow-sm shadow-zinc-900/5 dark:border-white/10 dark:bg-white/[0.04]"
          >
            <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ item.title }}</p>
            <p class="mt-1 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ item.body }}</p>
          </div>
        </div>
      </div>

      <div data-reveal class="reveal-on-scroll relative" style="--reveal-delay: 120ms">
        <div class="absolute -left-8 top-10 h-24 w-24 rounded-full bg-amber-200/60 blur-3xl dark:bg-amber-300/10" />
        <div class="absolute -right-2 bottom-6 h-32 w-32 rounded-full bg-teal-200/60 blur-3xl dark:bg-teal-300/10" />
        <div class="absolute inset-4 rounded-[2rem] border border-white/40 opacity-50" />
        <div class="grid-paper relative rounded-[2rem] border border-black/5 bg-white/92 p-4 shadow-[0_30px_90px_-30px_rgba(24,24,27,0.35)] dark:border-white/10 dark:bg-zinc-900/82 sm:p-5 lg:p-6">
          <div class="flex items-center justify-between border-b border-zinc-200/80 pb-4 dark:border-white/10">
            <div>
              <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ t('landing.hero.panel.title') }}</p>
              <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{{ t('landing.hero.panel.subtitle') }}</p>
            </div>
            <span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-300">
              {{ t('landing.hero.panel.status') }}
            </span>
          </div>

          <div class="mt-6 grid gap-4">
            <div class="grid gap-4 md:grid-cols-[1.05fr_0.95fr]">
              <div class="rounded-[1.5rem] border border-zinc-200/80 bg-stone-50/90 p-4 dark:border-white/10 dark:bg-white/[0.03]">
                <div class="flex items-center justify-between">
                  <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">{{ t('landing.hero.panel.queueLabel') }}</p>
                  <span class="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-zinc-700 shadow-sm dark:bg-white/10 dark:text-zinc-200">
                    {{ t('landing.hero.panel.queueStatus') }}
                  </span>
                </div>
                <div class="mt-4 space-y-3">
                  <div
                    v-for="card in workflowCards"
                    :key="card.title"
                    class="rounded-2xl border border-zinc-200/80 bg-white p-3 dark:border-white/10 dark:bg-zinc-950/40"
                  >
                    <div class="flex items-start justify-between gap-4">
                      <div>
                        <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ card.title }}</p>
                        <p class="mt-1 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ card.body }}</p>
                      </div>
                      <span class="rounded-full bg-zinc-950 px-2.5 py-1 text-xs font-semibold text-white dark:bg-white dark:text-zinc-950">
                        {{ card.metric }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="rounded-[1.5rem] border border-zinc-200/80 bg-zinc-950 p-4 text-white dark:border-white/10 dark:bg-white/[0.05]">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-amber-300">{{ t('landing.hero.panel.focusLabel') }}</p>
                <h3 class="mt-3 font-landing-display text-2xl tracking-[-0.03em]">{{ t('landing.hero.panel.focusTitle') }}</h3>
                <p class="mt-3 text-sm leading-6 text-zinc-300 dark:text-zinc-400">{{ t('landing.hero.panel.focusBody') }}</p>
                <div class="mt-5 grid gap-3 sm:grid-cols-2">
                  <div
                    v-for="item in focusMetrics"
                    :key="item.label"
                    class="rounded-2xl border border-white/10 bg-white/8 p-3"
                  >
                    <p class="text-xl font-semibold text-white dark:text-zinc-100">{{ item.value }}</p>
                    <p class="mt-1 text-xs uppercase tracking-[0.16em] text-zinc-300 dark:text-zinc-500">{{ item.label }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-5 rounded-2xl bg-zinc-950 p-4 text-white dark:bg-white dark:text-zinc-950">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] opacity-70">{{ t('landing.hero.panel.footerLabel') }}</p>
            <p class="mt-2 text-sm leading-6">{{ t('landing.hero.panel.footerText') }}</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t, tm } = useI18n()

const proofItems = computed(() => {
  const items = tm('landing.hero.proof')
  return Array.isArray(items) ? items : []
})

const workflowCards = computed(() => {
  const items = tm('landing.hero.workflowCards')
  return Array.isArray(items) ? items : []
})

const trustPills = computed(() => {
  const items = tm('landing.hero.trustPills')
  return Array.isArray(items) ? items : []
})

const focusMetrics = computed(() => {
  const items = tm('landing.hero.focusMetrics')
  return Array.isArray(items) ? items : []
})
</script>
