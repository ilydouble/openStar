<template>
  <section class="px-4 pb-8 sm:px-6 lg:px-8">
    <div class="mx-auto max-w-7xl">
      <div
        data-reveal
        class="reveal-on-scroll grid gap-5 rounded-[2rem] border border-black/5 bg-white/78 p-5 shadow-[0_24px_70px_-34px_rgba(24,24,27,0.28)] backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.04] lg:grid-cols-[0.78fr_1.22fr] lg:p-6"
      >
        <div class="rounded-[1.5rem] border border-black/5 bg-stone-50/90 p-5 dark:border-white/10 dark:bg-zinc-950/40">
          <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
            {{ t('landing.relatedBusiness.eyebrow') }}
          </p>
          <h2 class="mt-3 text-2xl font-semibold tracking-[-0.03em] text-zinc-950 dark:text-white">
            {{ t('landing.relatedBusiness.title') }}
          </h2>
          <p class="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-400">
            {{ t('landing.relatedBusiness.subtitle') }}
          </p>
          <a
            :href="apiSiteUrl"
            target="_blank"
            rel="noreferrer"
            class="mt-5 inline-flex items-center gap-2 rounded-full bg-zinc-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:scale-[1.02] dark:bg-white dark:text-zinc-950"
          >
            {{ t('landing.relatedBusiness.primaryCta') }}
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M9 7h8v8" />
            </svg>
          </a>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <article
            v-for="(item, index) in items"
            :key="item.title"
            class="reveal-on-scroll rounded-[1.5rem] border border-black/5 bg-white/88 p-5 shadow-sm shadow-zinc-900/5 dark:border-white/10 dark:bg-white/[0.04]"
            :style="{ '--reveal-delay': `${80 + index * 55}ms` }"
            data-reveal
          >
            <p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-500">
              {{ item.kicker }}
            </p>
            <h3 class="mt-3 text-lg font-semibold text-zinc-950 dark:text-white">
              {{ item.title }}
            </h3>
            <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
              {{ item.body }}
            </p>
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

const apiSiteUrl = 'https://api.stellarmesh.net'

const items = computed(() => {
  const raw = tm('landing.relatedBusiness.items')
  return Array.isArray(raw) ? raw : []
})
</script>
