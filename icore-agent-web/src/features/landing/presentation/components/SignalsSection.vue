<template>
  <section class="px-4 pb-8 sm:px-6 lg:px-8">
    <div class="mx-auto max-w-7xl">
      <div data-reveal class="reveal-on-scroll grid gap-4 rounded-[2rem] border border-black/5 bg-white/75 p-4 shadow-[0_20px_60px_-30px_rgba(24,24,27,0.25)] backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.04] lg:grid-cols-[1.1fr_0.9fr] lg:p-6">
        <div class="grid gap-4 sm:grid-cols-3">
          <article
            v-for="item in stats"
            :key="item.value"
            class="rounded-[1.5rem] border border-black/5 bg-stone-50/90 p-4 dark:border-white/10 dark:bg-zinc-950/40"
          >
            <p class="font-landing-display text-3xl text-zinc-950 dark:text-white">{{ item.value }}</p>
            <p class="mt-2 text-sm font-semibold text-zinc-800 dark:text-zinc-200">{{ item.label }}</p>
            <p class="mt-1 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ item.body }}</p>
          </article>
        </div>

        <div class="rounded-[1.5rem] border border-black/5 bg-zinc-950 px-5 py-4 text-white dark:border-white/10 dark:bg-white/[0.06]">
          <p class="text-xs font-semibold uppercase tracking-[0.18em] text-amber-300">{{ t('landing.signals.railLabel') }}</p>
          <div class="mt-4 flex flex-wrap gap-2.5">
            <span
              v-for="item in badges"
              :key="item"
              class="rounded-full border border-white/10 bg-white/8 px-3 py-1.5 text-xs font-semibold text-zinc-100 dark:bg-white/8"
            >
              {{ item }}
            </span>
          </div>
          <p class="mt-5 text-sm leading-6 text-zinc-300 dark:text-zinc-400">{{ t('landing.signals.railBody') }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { translatedArray } from '../../../../shared/presentation/i18n/translatedArray'

const { t, tm } = useI18n()

interface SignalStat { value: string; label: string; body: string }
const stats = computed(() => translatedArray<SignalStat>(tm, 'landing.signals.stats'))

const badges = computed(() => translatedArray<string>(tm, 'landing.signals.badges'))
</script>
