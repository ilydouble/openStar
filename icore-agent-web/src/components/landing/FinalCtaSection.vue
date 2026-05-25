<template>
  <section class="px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
    <div class="mx-auto max-w-7xl">
      <div data-reveal class="reveal-on-scroll relative overflow-hidden rounded-[2.5rem] border border-black/5 bg-[linear-gradient(135deg,#18181b_0%,#292524_55%,#115e59_100%)] px-6 py-10 text-white shadow-[0_36px_90px_-36px_rgba(24,24,27,0.8)] dark:border-white/10 lg:px-10 lg:py-12">
        <div class="absolute inset-y-0 right-0 w-1/2 bg-[radial-gradient(circle_at_top_right,rgba(251,191,36,0.35),transparent_38%)]" />
        <div class="absolute bottom-0 left-0 h-40 w-40 rounded-full bg-white/10 blur-3xl" />
        <div class="relative grid gap-8 lg:grid-cols-[1fr_0.9fr] lg:items-center">
          <div class="max-w-2xl">
            <p class="text-sm font-semibold uppercase tracking-[0.18em] text-amber-300">{{ t('landing.finalCta.eyebrow') }}</p>
            <h2 class="font-landing-display mt-4 text-4xl tracking-[-0.045em] sm:text-5xl">
              {{ t('landing.finalCta.title') }}
            </h2>
            <p class="mt-4 text-base leading-7 text-zinc-200 dark:text-zinc-300">
              {{ t('landing.finalCta.subtitle') }}
            </p>
            <div class="mt-8 flex flex-col gap-3 sm:flex-row">
              <RouterLink
                to="/auth"
                class="inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-zinc-950 transition hover:scale-[1.02]"
              >
                {{ t('landing.finalCta.primary') }}
              </RouterLink>
              <a
                href="#plans"
                class="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/8 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/12"
              >
                {{ t('landing.finalCta.secondary') }}
              </a>
            </div>
          </div>

          <div class="overflow-hidden rounded-[2rem] border border-white/10 bg-black/20 shadow-[0_28px_80px_-40px_rgba(0,0,0,0.85)]">
            <img
              :src="finalCtaImage"
              alt=""
              class="h-full w-full object-cover object-center"
            >
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import finalCtaImage from '../../assets/landing/final-cta-platform.jpg'

const { t } = useI18n()
</script>
