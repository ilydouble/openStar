<template>
  <div class="min-h-screen bg-[radial-gradient(circle_at_top,#fff7ed,transparent_38%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] px-4 py-8 text-zinc-950 dark:bg-[radial-gradient(circle_at_top,#312e81,transparent_28%),linear-gradient(180deg,#09090b_0%,#18181b_100%)] dark:text-white">
    <div class="mx-auto flex min-h-[calc(100vh-4rem)] max-w-6xl items-center">
      <div class="grid w-full gap-8 lg:grid-cols-[1.05fr_0.95fr]">
        <section class="rounded-[2rem] border border-white/70 bg-white/80 p-8 shadow-[0_32px_80px_-32px_rgba(15,23,42,0.3)] backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.06] dark:shadow-[0_40px_90px_-30px_rgba(0,0,0,0.55)]">
          <p class="text-xs font-semibold uppercase tracking-[0.24em] text-amber-600 dark:text-amber-300">
            {{ t('auth.eyebrow') }}
          </p>
          <h1 class="mt-4 max-w-xl text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">
            {{ t('auth.title') }}
          </h1>
          <p class="mt-4 max-w-xl text-base leading-7 text-zinc-600 dark:text-zinc-300">
            {{ t('auth.subtitle') }}
          </p>
          <div class="mt-8 grid gap-4 sm:grid-cols-3">
            <article
              v-for="item in featureCards"
              :key="item.title"
              class="rounded-2xl border border-zinc-200/80 bg-zinc-50/90 p-4 dark:border-white/10 dark:bg-white/[0.04]"
            >
              <p class="text-sm font-semibold">{{ item.title }}</p>
              <p class="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{{ item.body }}</p>
            </article>
          </div>
        </section>

        <section class="rounded-[2rem] border border-zinc-200/80 bg-white/92 p-8 shadow-[0_28px_70px_-30px_rgba(15,23,42,0.32)] dark:border-white/10 dark:bg-zinc-950/72">
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-sm font-semibold text-zinc-800 dark:text-zinc-100">{{ t('auth.formTitle') }}</p>
              <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{{ t('auth.formHint') }}</p>
            </div>
            <RouterLink to="/" class="text-sm font-medium text-zinc-500 transition hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-white">
              {{ t('auth.backHome') }}
            </RouterLink>
          </div>

          <form class="mt-8 space-y-5" @submit.prevent="submit">
            <label class="block">
              <span class="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-200">{{ t('auth.name') }}</span>
              <input
                v-model="form.name"
                type="text"
                required
                class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10"
              />
            </label>
            <label class="block">
              <span class="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-200">{{ t('auth.email') }}</span>
              <input
                v-model="form.email"
                type="email"
                required
                class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10"
              />
            </label>
            <button
              type="submit"
              :disabled="submitting"
              class="w-full rounded-2xl bg-zinc-950 px-5 py-3 text-sm font-semibold text-white transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-zinc-950"
            >
              {{ submitting ? t('auth.loading') : t('auth.submit') }}
            </button>
            <p v-if="error" class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
              {{ error }}
            </p>
          </form>

          <div class="mt-8 rounded-2xl border border-zinc-200/80 bg-zinc-50/85 p-4 dark:border-white/10 dark:bg-white/[0.04]">
            <p class="text-xs font-semibold uppercase tracking-[0.22em] text-zinc-500 dark:text-zinc-400">{{ t('auth.trialLabel') }}</p>
            <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-300">{{ t('auth.trialSummary') }}</p>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { registerTrial } from '../api/account.js'

const { t, tm } = useI18n()
const router = useRouter()

const form = reactive({
  name: '',
  email: '',
})
const submitting = ref(false)
const error = ref('')

const featureCards = computed(() => {
  const raw = tm('auth.features')
  return Array.isArray(raw) ? raw : []
})

async function submit() {
  if (submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await registerTrial(form)
    router.push({ name: 'workspace' })
  } catch (err) {
    error.value = err.message || t('auth.failed')
  } finally {
    submitting.value = false
  }
}
</script>
