<template>
  <section id="plans" class="px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
    <div class="mx-auto max-w-7xl">
      <div data-reveal class="reveal-on-scroll flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="max-w-2xl">
          <p class="text-sm font-semibold uppercase tracking-[0.18em] text-rose-700 dark:text-rose-300">
            {{ t('landing.plans.eyebrow') }}
          </p>
          <h2 class="mt-4 text-3xl font-semibold tracking-[-0.04em] text-zinc-950 dark:text-white sm:text-4xl">
            {{ t('landing.plans.title') }}
          </h2>
          <p class="mt-4 text-base leading-7 text-zinc-600 dark:text-zinc-400">
            {{ t('landing.plans.subtitle') }}
          </p>
        </div>
        <RouterLink
          to="/auth"
          class="inline-flex items-center justify-center rounded-full border border-zinc-200 bg-white px-5 py-3 text-sm font-semibold text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/5 dark:text-zinc-200"
        >
          {{ t('landing.plans.cta') }}
        </RouterLink>
      </div>

      <div class="mt-10 grid gap-5 lg:grid-cols-3">
        <article
          v-for="tier in tiers"
          :key="tier.name"
          :class="[
            'reveal-on-scroll rounded-[2rem] border p-6 shadow-sm transition duration-300',
            tier.featured
              ? 'border-zinc-950 bg-zinc-950 text-white shadow-[0_30px_80px_-35px_rgba(24,24,27,0.75)] dark:border-white dark:bg-white dark:text-zinc-950'
              : 'border-black/5 bg-white/85 text-zinc-950 shadow-zinc-900/5 dark:border-white/10 dark:bg-white/[0.04] dark:text-white',
          ]"
          :style="{ '--reveal-delay': `${100 + tiers.indexOf(tier) * 70}ms` }"
          data-reveal
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <h3 class="text-2xl font-semibold">{{ tier.name }}</h3>
              <p :class="tier.featured ? 'mt-2 text-sm text-zinc-300 dark:text-zinc-700' : 'mt-2 text-sm text-zinc-600 dark:text-zinc-400'">
                {{ tier.audience }}
              </p>
            </div>
            <span
              v-if="tier.badge"
              :class="tier.featured ? 'rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white dark:bg-zinc-950/10 dark:text-zinc-950' : 'rounded-full bg-zinc-950 px-3 py-1 text-xs font-semibold text-white dark:bg-white dark:text-zinc-950'"
            >
              {{ tier.badge }}
            </span>
          </div>

          <div class="mt-4 flex items-baseline gap-1">
            <span class="text-3xl font-bold tracking-tight">{{ tier.price }}</span>
            <span :class="tier.featured ? 'text-sm text-zinc-300 dark:text-zinc-700' : 'text-sm text-zinc-500 dark:text-zinc-400'">{{ tier.period }}</span>
          </div>

          <p :class="tier.featured ? 'mt-6 text-sm leading-6 text-zinc-200 dark:text-zinc-700' : 'mt-6 text-sm leading-6 text-zinc-600 dark:text-zinc-400'">
            {{ tier.description }}
          </p>

          <ul class="mt-6 space-y-3">
            <li
              v-for="feature in tier.features"
              :key="feature"
              class="flex items-start gap-3 text-sm leading-6"
            >
              <span :class="tier.featured ? 'mt-1 h-2 w-2 rounded-full bg-amber-300 dark:bg-zinc-950' : 'mt-1 h-2 w-2 rounded-full bg-zinc-950 dark:bg-white'" />
              <span>{{ feature }}</span>
            </li>
          </ul>

          <div class="mt-8">
            <RouterLink
              :to="tier.link || '/auth'"
              :class="tier.featured
                ? 'inline-flex items-center justify-center rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-zinc-950 transition hover:scale-[1.02] dark:bg-zinc-950 dark:text-white'
                : 'inline-flex items-center justify-center rounded-full border border-zinc-200 bg-white px-5 py-2.5 text-sm font-semibold text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/[0.05] dark:text-zinc-100'"
            >
              {{ tier.cta }}
            </RouterLink>
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

const { t, tm } = useI18n()
const tiers = computed(() => {
  const raw = tm('landing.plans.tiers')
  return Array.isArray(raw) ? raw : []
})
</script>
