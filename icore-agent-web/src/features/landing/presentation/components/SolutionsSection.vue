<template>
  <section id="solutions" class="px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
    <div class="mx-auto max-w-7xl">
      <div data-reveal class="reveal-on-scroll max-w-2xl">
        <p class="text-sm font-semibold uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">
          {{ t('landing.solutions.eyebrow') }}
        </p>
        <h2 class="mt-4 text-3xl font-semibold tracking-[-0.04em] text-zinc-950 dark:text-white sm:text-4xl">
          {{ t('landing.solutions.title') }}
        </h2>
        <p class="mt-4 text-base leading-7 text-zinc-600 dark:text-zinc-400">
          {{ t('landing.solutions.subtitle') }}
        </p>
      </div>

      <div
        data-reveal
        class="reveal-on-scroll relative mt-10 overflow-hidden rounded-[2.25rem] border border-black/5 bg-zinc-950 shadow-[0_30px_80px_-38px_rgba(24,24,27,0.65)] dark:border-white/10"
        style="--reveal-delay: 80ms"
      >
        <img
          :src="solutionsImage"
          alt=""
          class="h-[240px] w-full object-cover object-center opacity-90 sm:h-[300px]"
        >
        <div class="absolute inset-0 bg-[linear-gradient(180deg,rgba(9,9,11,0.06),rgba(9,9,11,0.4))]" />
      </div>

      <div class="mt-10 grid gap-5 lg:grid-cols-6">
        <article
          v-for="(item, index) in items"
          :key="item.title"
          :class="[
            'reveal-on-scroll group rounded-[2rem] border border-black/5 bg-white/85 p-5 shadow-sm shadow-zinc-900/5 transition duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-zinc-900/10 dark:border-white/10 dark:bg-white/[0.04]',
            index === 0 ? 'lg:col-span-2 lg:row-span-2 bg-[linear-gradient(180deg,rgba(255,251,235,0.95),rgba(255,255,255,0.88))] dark:bg-[linear-gradient(180deg,rgba(24,24,27,0.92),rgba(255,255,255,0.04))]' : 'lg:col-span-2',
          ]"
          :style="{ '--reveal-delay': `${100 + index * 60}ms` }"
          data-reveal
        >
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-950 text-lg text-white dark:bg-white dark:text-zinc-950">
            {{ item.icon }}
          </div>
          <div class="mt-5 flex items-start justify-between gap-4">
            <h3 :class="index === 0 ? 'font-landing-display text-2xl tracking-[-0.03em] text-zinc-950 dark:text-white' : 'text-lg font-semibold text-zinc-950 dark:text-white'">
              {{ item.title }}
            </h3>
            <span class="rounded-full border border-zinc-200 bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-700 dark:border-white/10 dark:bg-white/[0.05] dark:text-zinc-300">
              {{ item.tag }}
            </span>
          </div>
          <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ item.body }}</p>
          <div class="mt-6 border-t border-zinc-200/80 pt-4 dark:border-white/10">
            <p class="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-500">{{ t('landing.solutions.outcomeLabel') }}</p>
            <p class="mt-2 text-sm font-semibold text-zinc-950 dark:text-white">{{ item.outcome }}</p>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import solutionsImage from '../../assets/solutions-workflows.jpg'
import { translatedArray } from '../../../../shared/presentation/i18n/translatedArray'

const { t, tm } = useI18n()
interface SolutionItem {
  icon: string
  title: string
  tag: string
  body: string
  outcome: string
}
const items = computed(() => translatedArray<SolutionItem>(tm, 'landing.solutions.items'))
</script>
