<template>
  <div class="min-h-screen bg-[radial-gradient(circle_at_top,#fef3c7,transparent_26%),linear-gradient(180deg,#fafaf9_0%,#f5f5f4_100%)] px-4 py-8 text-zinc-950 dark:bg-[radial-gradient(circle_at_top,#134e4a,transparent_22%),linear-gradient(180deg,#09090b_0%,#18181b_100%)] dark:text-white">
    <div class="mx-auto max-w-6xl">
      <div class="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
        <section class="rounded-[2rem] border border-white/70 bg-white/85 p-8 shadow-[0_32px_80px_-32px_rgba(15,23,42,0.28)] dark:border-white/10 dark:bg-white/[0.05]">
          <p class="text-xs font-semibold uppercase tracking-[0.22em] text-amber-700 dark:text-amber-300">{{ t('enterprise.eyebrow') }}</p>
          <h1 class="mt-4 text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">{{ t('enterprise.title') }}</h1>
          <p class="mt-4 max-w-2xl text-base leading-7 text-zinc-600 dark:text-zinc-300">{{ t('enterprise.subtitle') }}</p>
          <div class="mt-8 grid gap-4 sm:grid-cols-3">
            <article
              v-for="item in valueCards"
              :key="item.title"
              class="rounded-2xl border border-zinc-200/80 bg-zinc-50/85 p-4 dark:border-white/10 dark:bg-white/[0.04]"
            >
              <p class="text-sm font-semibold">{{ item.title }}</p>
              <p class="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ item.body }}</p>
            </article>
          </div>
        </section>

        <section class="rounded-[2rem] border border-zinc-200/80 bg-white/92 p-8 shadow-[0_28px_70px_-30px_rgba(15,23,42,0.3)] dark:border-white/10 dark:bg-zinc-950/72">
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-sm font-semibold text-zinc-800 dark:text-zinc-100">{{ t('enterprise.formTitle') }}</p>
              <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{{ t('enterprise.formHint') }}</p>
            </div>
            <RouterLink to="/" class="text-sm font-medium text-zinc-500 transition hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-white">
              {{ t('enterprise.backHome') }}
            </RouterLink>
          </div>

          <form class="mt-8 grid gap-4" @submit.prevent="submit">
            <div class="grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('enterprise.name') }}</span>
                <input v-model="form.name" type="text" required class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-400 focus:ring-4 focus:ring-teal-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-teal-300 dark:focus:ring-teal-500/10" />
              </label>
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('enterprise.email') }}</span>
                <input v-model="form.email" type="email" required class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-400 focus:ring-4 focus:ring-teal-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-teal-300 dark:focus:ring-teal-500/10" />
              </label>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('enterprise.company') }}</span>
                <input v-model="form.company" type="text" class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-400 focus:ring-4 focus:ring-teal-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-teal-300 dark:focus:ring-teal-500/10" />
              </label>
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('enterprise.teamSize') }}</span>
                <select v-model="form.team_size" class="form-select form-select-teal">
                  <option value="1-10">1-10</option>
                  <option value="11-50">11-50</option>
                  <option value="51-200">51-200</option>
                  <option value="200+">200+</option>
                </select>
              </label>
            </div>

            <label class="block">
              <span class="mb-2 block text-sm font-medium">{{ t('enterprise.useCase') }}</span>
              <textarea v-model="form.use_case" rows="5" class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-400 focus:ring-4 focus:ring-teal-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-teal-300 dark:focus:ring-teal-500/10" />
            </label>

            <div class="grid gap-3 md:grid-cols-2">
              <label class="flex items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm dark:border-white/10 dark:bg-white/[0.04]">
                <input v-model="form.needs_byok" type="checkbox" class="h-4 w-4 rounded border-zinc-300 text-teal-600 focus:ring-teal-500" />
                <span>{{ t('enterprise.needsByok') }}</span>
              </label>
              <label class="flex items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm dark:border-white/10 dark:bg-white/[0.04]">
                <input v-model="form.needs_private_deploy" type="checkbox" class="h-4 w-4 rounded border-zinc-300 text-teal-600 focus:ring-teal-500" />
                <span>{{ t('enterprise.needsPrivateDeploy') }}</span>
              </label>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('enterprise.intent') }}</span>
                <select v-model="form.intent" class="form-select form-select-teal">
                  <option value="demo">{{ t('enterprise.intentOptions.demo') }}</option>
                  <option value="enterprise">{{ t('enterprise.intentOptions.enterprise') }}</option>
                  <option value="upgrade-team">{{ t('enterprise.intentOptions.team') }}</option>
                  <option value="upgrade-enterprise">{{ t('enterprise.intentOptions.upgradeEnterprise') }}</option>
                </select>
              </label>
              <div class="flex items-end">
                <button type="submit" :disabled="submitting" class="w-full rounded-2xl bg-zinc-950 px-5 py-3 text-sm font-semibold text-white transition hover:scale-[1.01] disabled:opacity-60 dark:bg-white dark:text-zinc-950">
                  {{ submitting ? t('enterprise.loading') : t('enterprise.submit') }}
                </button>
              </div>
            </div>

            <p v-if="success" class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
              {{ t('enterprise.success') }}
            </p>
            <p v-if="error" class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
              {{ error }}
            </p>
          </form>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { captureLead } from '../api/account.js'

const { t, tm } = useI18n()
const route = useRoute()
const submitting = ref(false)
const success = ref(false)
const error = ref('')

const form = reactive({
  name: '',
  email: '',
  company: '',
  team_size: route.query.plan === 'enterprise' ? '51-200' : '11-50',
  use_case: '',
  needs_byok: route.query.plan === 'enterprise',
  needs_private_deploy: false,
  source: 'enterprise-page',
  intent: route.query.intent || (route.query.plan === 'team' ? 'upgrade-team' : route.query.plan === 'enterprise' ? 'upgrade-enterprise' : 'demo'),
})

const valueCards = computed(() => {
  const raw = tm('enterprise.cards')
  return Array.isArray(raw) ? raw : []
})

async function submit() {
  if (submitting.value) return
  submitting.value = true
  success.value = false
  error.value = ''
  try {
    await captureLead(form)
    success.value = true
  } catch (err) {
    error.value = err.message || t('enterprise.failed')
  } finally {
    submitting.value = false
  }
}
</script>
