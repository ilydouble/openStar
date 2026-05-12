<template>
  <footer class="relative z-10 border-t border-black/5 px-4 py-10 dark:border-white/10 sm:px-6 lg:px-8">
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
          <a
            :href="apiSiteUrl"
            target="_blank"
            rel="noreferrer"
            class="rounded-full border border-zinc-200 bg-white px-3 py-1.5 font-medium text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300 dark:hover:text-white"
          >
            {{ t('landing.footer.relatedSiteLabel') }}: api.stellarmesh.net
          </a>
        </div>
      </div>

      <div class="flex flex-col gap-4 text-sm text-zinc-600 dark:text-zinc-400 sm:flex-row sm:items-center">
        <a href="#solutions" class="transition hover:text-zinc-950 dark:hover:text-white">{{ t('landing.footer.links.solutions') }}</a>
        <a href="#plans" class="transition hover:text-zinc-950 dark:hover:text-white">{{ t('landing.footer.links.plans') }}</a>
        <button type="button" class="text-left transition hover:text-zinc-950 dark:hover:text-white" @click="toggleLocale">
          {{ t('landing.footer.language') }}: {{ currentLocale === 'zh-CN' ? 'English' : '中文' }}
        </button>
        <RouterLink to="/auth" class="transition hover:text-zinc-950 dark:hover:text-white">{{ t('landing.footer.links.signIn') }}</RouterLink>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const currentLocale = computed(() => locale.value)
const primaryDomain = 'www.stellarmesh.net'
const primaryDomainUrl = `https://${primaryDomain}`
const apiSiteUrl = 'https://api.stellarmesh.net'

function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  localStorage.setItem('locale', locale.value)
}
</script>
