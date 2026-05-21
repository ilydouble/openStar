<template>
  <section id="why" class="px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
    <div class="mx-auto max-w-7xl">
      <div class="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
        <div data-reveal class="reveal-on-scroll max-w-xl">
          <p class="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
            {{ t('landing.why.eyebrow') }}
          </p>
          <h2 class="mt-4 text-3xl font-semibold tracking-[-0.04em] text-zinc-950 dark:text-white sm:text-4xl">
            {{ t('landing.why.title') }}
          </h2>
          <p class="mt-4 text-base leading-7 text-zinc-600 dark:text-zinc-400">
            {{ t('landing.why.subtitle') }}
          </p>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <article
            v-for="item in items"
            :key="item.title"
            class="reveal-on-scroll rounded-[1.75rem] border border-black/5 bg-white/85 p-5 shadow-sm shadow-zinc-900/5 transition duration-300 hover:-translate-y-1 hover:shadow-lg hover:shadow-zinc-900/10 dark:border-white/10 dark:bg-white/[0.04]"
            :style="{ '--reveal-delay': `${90 + items.indexOf(item) * 50}ms` }"
            data-reveal
          >
            <p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-500">{{ item.kicker }}</p>
            <h3 class="mt-3 text-lg font-semibold text-zinc-950 dark:text-white">{{ item.title }}</h3>
            <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ item.body }}</p>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, tm } = useI18n()
const items = computed(() => {
  const raw = tm('landing.why.items')
  return Array.isArray(raw) ? raw : []
})
</script>
