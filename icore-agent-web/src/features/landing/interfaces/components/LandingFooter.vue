<template>
  <footer class="relative z-10 border-t border-black/5 dark:border-white/10">
    <div class="px-4 py-10 sm:px-6 lg:px-8">
      <div class="mx-auto flex max-w-7xl flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div class="max-w-2xl">
          <p class="text-lg font-semibold text-zinc-950 dark:text-white">{{ t('landing.footer.title') }}</p>
          <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ t('landing.footer.subtitle') }}</p>
          <div class="mt-4 flex flex-wrap items-center gap-3 text-sm">
            <a
              :href="primaryDomainUrl"
              target="_blank"
              rel="noreferrer"
              class="rounded-full border border-zinc-200 bg-white px-3 py-1.5 font-medium text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300 dark:hover:text-white"
            >
              {{ t('landing.footer.primaryDomainLabel') }}: {{ primaryDomain }}
            </a>
          </div>
        </div>

        <div class="flex flex-col gap-4 text-sm text-zinc-600 dark:text-zinc-400 sm:flex-row sm:items-center">
          <a href="#solutions" class="transition hover:text-zinc-950 dark:hover:text-white">{{ t('landing.footer.links.solutions') }}</a>
          <a href="#plans" class="transition hover:text-zinc-950 dark:hover:text-white">{{ t('landing.footer.links.plans') }}</a>
          <button type="button" class="text-left transition hover:text-zinc-950 dark:hover:text-white" @click="toggleLocale">
            {{ t('landing.footer.language') }}:
            {{
              currentLocale === 'zh-CN' ? t('common.localeNameEnglish') : t('common.localeNameChinese')
            }}
          </button>
          <RouterLink to="/auth" class="transition hover:text-zinc-950 dark:hover:text-white">{{ t('landing.footer.links.signIn') }}</RouterLink>
        </div>
      </div>
    </div>

    <div class="border-t border-black/5 bg-black/[0.03] px-4 py-4 dark:border-white/10 dark:bg-white/[0.03] sm:px-6 lg:px-8">
      <div class="mx-auto flex max-w-7xl flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
            {{ t('landing.footer.extraServicesLabel') }}
          </p>
          <p class="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            {{ t('landing.footer.extraServicesIntro') }}
          </p>
        </div>

        <div class="flex flex-wrap gap-3">
          <a
            v-for="service in extraServices"
            :key="service.name"
            :href="service.href"
            target="_blank"
            rel="noreferrer"
            class="group min-w-[280px] rounded-2xl border border-zinc-200 bg-white px-4 py-3 transition hover:border-zinc-300 hover:bg-zinc-50 dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.06]"
          >
            <div class="flex items-center justify-between gap-3">
              <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ service.name }}</p>
              <span class="text-xs uppercase tracking-[0.16em] text-zinc-400 transition group-hover:text-zinc-600 dark:group-hover:text-zinc-300">
                {{ service.tag }}
              </span>
            </div>
            <p class="mt-1 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ service.description }}</p>
          </a>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocalePreference } from '../../../../shared/i18n/localePreference'

const { t, tm, locale } = useI18n()
const currentLocale = computed(() => locale.value)
const primaryDomain = 'www.stellarmesh.net'
const primaryDomainUrl = `https://${primaryDomain}`
const extraServices = computed(() => {
  const items = tm('landing.footer.extraServices')
  return Array.isArray(items) ? items : []
})

/**
 * Toggle the marketing site locale and persist the user's selection locally.
 */
function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  setLocalePreference(locale.value)
}
</script>
