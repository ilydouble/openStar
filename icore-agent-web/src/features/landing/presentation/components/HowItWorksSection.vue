<template>
  <section id="workflows" class="px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
    <div data-reveal class="reveal-on-scroll mx-auto grid max-w-7xl gap-10 rounded-[2rem] border border-black/5 bg-zinc-950 px-6 py-8 text-white shadow-[0_30px_90px_-35px_rgba(24,24,27,0.7)] dark:border-white/10 dark:bg-white/[0.04] dark:shadow-none lg:grid-cols-[0.9fr_1.1fr] lg:px-10 lg:py-12">
      <div>
        <p class="text-sm font-semibold uppercase tracking-[0.18em] text-amber-300">{{ t('landing.workflow.eyebrow') }}</p>
        <h2 class="font-landing-display mt-4 text-4xl tracking-[-0.045em] sm:text-5xl">{{ t('landing.workflow.title') }}</h2>
        <p class="mt-4 text-base leading-7 text-zinc-300 dark:text-zinc-400">{{ t('landing.workflow.subtitle') }}</p>
        <div class="mt-6 rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
          <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-400">{{ t('landing.workflow.callout.label') }}</p>
          <p class="mt-3 text-sm leading-6 text-zinc-200 dark:text-zinc-300">{{ t('landing.workflow.callout.body') }}</p>
        </div>
      </div>

      <div class="grid gap-4 md:grid-cols-3">
        <article
          v-for="(step, index) in steps"
          :key="step.title"
          class="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 backdrop-blur transition duration-300 hover:-translate-y-1 hover:bg-white/8"
        >
          <p class="text-sm font-semibold text-amber-300">0{{ index + 1 }}</p>
          <h3 class="mt-3 text-lg font-semibold">{{ step.title }}</h3>
          <p class="mt-3 text-sm leading-6 text-zinc-300 dark:text-zinc-400">{{ step.body }}</p>
          <div class="mt-5 h-1.5 rounded-full bg-white/8">
            <div class="h-full rounded-full bg-amber-300" :style="{ width: `${step.progress}%` }" />
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { translatedArray } from '../../../../shared/presentation/i18n/translatedArray'

const { t, tm } = useI18n()
interface WorkflowStep { title: string; body: string; progress: number }
const steps = computed(() => translatedArray<WorkflowStep>(tm, 'landing.workflow.steps'))
</script>
