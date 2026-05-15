<template>
  <section class="relative overflow-hidden px-4 pb-10 pt-10 sm:px-6 lg:px-8 lg:pb-18 lg:pt-24">
    <div class="mx-auto grid min-w-0 max-w-7xl gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.9fr)] lg:items-start">
      <div data-reveal class="reveal-on-scroll min-w-0">
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

      <div
        data-reveal
        class="reveal-on-scroll relative mx-auto w-full max-w-xl min-w-0 lg:mx-0 lg:max-w-none"
        style="--reveal-delay: 120ms"
      >
        <!-- Soft ambient (single layer, clipped) -->
        <div class="pointer-events-none absolute inset-0 -z-10 overflow-visible sm:overflow-hidden sm:rounded-3xl">
          <div
            class="absolute -right-[15%] -top-[20%] hidden h-[min(22rem,50vw)] w-[min(20rem,45vw)] rounded-full bg-teal-500/[0.08] blur-[56px] sm:block dark:bg-teal-400/[0.1]"
          />
          <div
            class="absolute -bottom-[18%] -left-[12%] h-[min(18rem,45vw)] w-[min(16rem,40vw)] rounded-full bg-violet-500/[0.085] blur-[48px] dark:bg-violet-400/[0.1]"
          />
        </div>

        <!-- Dashboard shell -->
        <article
          class="relative overflow-hidden rounded-[1.25rem] border border-zinc-200/90 bg-gradient-to-b from-white via-white to-stone-50/55 shadow-[0_2px_0_1px_rgba(255,255,255,0.92)_inset,0_20px_52px_-24px_rgba(24,24,27,0.11)] ring-1 ring-zinc-200/40 backdrop-blur-sm dark:border-white/[0.085] dark:bg-gradient-to-b dark:from-zinc-950 dark:via-zinc-950 dark:to-zinc-900 dark:shadow-[0_1px_0_1px_rgba(255,255,255,0.04)_inset,0_24px_56px_-28px_rgba(0,0,0,0.52)] dark:ring-white/[0.06] sm:rounded-3xl"
        >
          <!-- Watermark -->
          <div class="pointer-events-none absolute inset-0 select-none opacity-[0.052] dark:opacity-[0.032]">
            <img :src="heroBackdropImage" alt="" class="h-full w-full object-cover object-[50%_18%]" />
            <div
              class="absolute inset-0 bg-gradient-to-br from-white via-white/94 to-stone-100 dark:from-zinc-950 dark:via-zinc-950/94 dark:to-zinc-950"
            />
          </div>

          <div class="relative flex flex-col gap-5 p-4 sm:gap-6 sm:p-5 lg:p-6">
            <!-- Top chrome -->
            <header
              class="flex flex-col gap-4 border-b border-zinc-200/85 pb-5 dark:border-white/[0.07] sm:flex-row sm:items-start sm:justify-between sm:gap-5"
            >
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2 gap-y-2">
                  <span
                    class="h-2 w-2 shrink-0 rounded-full bg-emerald-600 ring-[3px] ring-emerald-500/25 dark:bg-emerald-400 dark:ring-emerald-400/18"
                    aria-hidden="true"
                  />
                  <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">
                    {{ t('landing.hero.panel.title') }}
                  </p>
                </div>
                <p
                  class="mt-3 text-[15px] font-semibold leading-snug tracking-tight text-zinc-900 sm:text-base sm:leading-6 dark:text-zinc-100"
                >
                  {{ t('landing.hero.panel.subtitle') }}
                </p>
              </div>
              <div class="flex shrink-0 sm:justify-end">
                <span
                  class="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50/95 px-4 py-1.5 text-xs font-semibold text-emerald-900 ring-1 ring-emerald-100/90 dark:border-emerald-400/35 dark:bg-emerald-400/14 dark:text-emerald-200 dark:ring-emerald-400/15"
                >
                  {{ t('landing.hero.panel.status') }}
                </span>
              </div>
            </header>

            <!-- Operations queue -->
            <section
              class="overflow-hidden rounded-2xl border border-zinc-200/85 bg-white shadow-sm shadow-zinc-900/[0.05] ring-1 ring-zinc-100/90 dark:border-white/[0.08] dark:bg-zinc-950 dark:shadow-none dark:ring-white/[0.06]"
            >
              <div
                class="flex flex-col gap-3 border-b border-zinc-200/80 bg-stone-50/95 px-4 py-3.5 dark:border-white/[0.07] dark:bg-zinc-900 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-4"
              >
                <h2 class="text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500 dark:text-zinc-400">
                  {{ t('landing.hero.panel.queueLabel') }}
                </h2>
                <span
                  class="w-fit shrink-0 rounded-full border border-zinc-200/95 bg-white px-3 py-1 text-[11px] font-semibold tabular-nums text-zinc-800 shadow-sm ring-1 ring-zinc-950/[0.04] dark:border-zinc-600/80 dark:bg-zinc-800 dark:text-zinc-100 dark:ring-zinc-500/20"
                >
                  {{ t('landing.hero.panel.queueStatus') }}
                </span>
              </div>
              <ul
                class="divide-y divide-zinc-200/65 bg-white dark:divide-white/[0.055] dark:bg-zinc-950"
                role="list"
              >
                <li
                  v-for="card in workflowCards"
                  :key="card.title"
                  class="group/item relative flex gap-0 transition-colors hover:bg-stone-50/90 dark:hover:bg-zinc-900/85"
                >
                  <span
                    class="w-1 shrink-0 rounded-l-xl bg-gradient-to-b from-violet-600 to-indigo-600 opacity-95 dark:from-violet-400 dark:to-indigo-500 dark:opacity-[0.92]"
                    aria-hidden="true"
                  />
                  <div
                    class="flex min-w-0 flex-1 flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between sm:gap-5 sm:p-4 sm:py-4 sm:pr-4"
                  >
                    <div class="min-w-0">
                      <p class="text-[15px] font-semibold leading-tight tracking-tight text-zinc-950 dark:text-zinc-100">
                        {{ card.title }}
                      </p>
                      <p class="mt-1.5 text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-400">
                        {{ card.body }}
                      </p>
                    </div>
                    <span
                      class="inline-flex shrink-0 self-start rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-center text-[11px] font-bold tabular-nums uppercase tracking-wide text-white shadow-sm dark:border-zinc-500/35 dark:bg-zinc-800 dark:text-zinc-50 dark:shadow-none"
                    >
                      {{ card.metric }}
                    </span>
                  </div>
                </li>
              </ul>
            </section>

            <!-- Focus & KPI -->
            <section
              class="overflow-hidden rounded-2xl border border-zinc-200/85 bg-white shadow-[0_8px_28px_-16px_rgba(24,24,27,0.14)] ring-1 ring-zinc-100/95 dark:border-white/[0.08] dark:bg-zinc-950 dark:shadow-[0_12px_40px_-24px_rgba(0,0,0,0.48)] dark:ring-white/[0.06]"
            >
              <div
                class="border-b border-zinc-200/80 bg-gradient-to-br from-white to-stone-50/85 px-4 py-5 sm:px-5 dark:border-white/[0.07] dark:bg-gradient-to-br dark:from-zinc-900 dark:to-zinc-950"
              >
                <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-700 dark:text-amber-200/90">
                  {{ t('landing.hero.panel.focusLabel') }}
                </p>
                <h3
                  class="font-landing-display mt-3 text-xl font-semibold leading-[1.2] tracking-[-0.028em] text-zinc-950 sm:text-[1.35rem] dark:text-white"
                >
                  {{ t('landing.hero.panel.focusTitle') }}
                </h3>
                <p class="mt-3 text-[13px] leading-relaxed text-zinc-600 sm:text-sm dark:text-zinc-400">
                  {{ t('landing.hero.panel.focusBody') }}
                </p>
              </div>
              <div class="grid grid-cols-2 gap-px bg-zinc-200/75 dark:bg-zinc-800/60">
                <div
                  v-for="item in focusMetrics"
                  :key="item.label"
                  class="flex min-h-[5.75rem] min-w-0 flex-col justify-center bg-white px-4 py-4 sm:min-h-[6.25rem] sm:px-5 dark:bg-zinc-950"
                >
                  <p
                    class="text-[clamp(1.125rem,2.8vw,1.375rem)] font-semibold tabular-nums tracking-tight text-zinc-950 dark:text-white"
                  >
                    {{ item.value }}
                  </p>
                  <p class="mt-2 text-[10px] font-medium uppercase tracking-[0.12em] text-zinc-500 dark:text-zinc-400">
                    {{ item.label }}
                  </p>
                </div>
              </div>
            </section>

            <!-- System note -->
            <footer
              class="rounded-xl border border-zinc-200/85 bg-stone-50/95 px-4 py-4 text-left shadow-sm shadow-zinc-900/[0.03] ring-1 ring-zinc-200/55 dark:border-white/[0.08] dark:bg-zinc-900 dark:shadow-none dark:ring-white/[0.04] sm:rounded-2xl sm:px-5 sm:py-4"
            >
              <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">
                {{ t('landing.hero.panel.footerLabel') }}
              </p>
              <p class="mt-3 text-[13px] leading-relaxed text-zinc-700 sm:text-sm dark:text-zinc-300">
                {{ t('landing.hero.panel.footerText') }}
              </p>
            </footer>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import heroBackdropImage from '../../assets/landing/hero-ops-cockpit.jpg'

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
