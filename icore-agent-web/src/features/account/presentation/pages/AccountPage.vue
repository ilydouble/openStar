<template>
  <div class="min-h-dvh overflow-x-hidden bg-zinc-100 px-3 py-5 text-zinc-950 dark:bg-zinc-950 dark:text-white sm:px-4 sm:py-6">
    <div class="mx-auto max-w-6xl">
      <div class="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold uppercase tracking-[0.22em] text-zinc-500 dark:text-zinc-400">{{ t('account.eyebrow') }}</p>
          <h1 class="mt-2 text-2xl font-semibold tracking-[-0.03em] min-[375px]:text-3xl">{{ t('account.title') }}</h1>
          <p class="mt-2 max-w-xl text-sm text-zinc-600 dark:text-zinc-300">{{ t('account.subtitle') }}</p>
        </div>
        <div class="flex w-full shrink-0 flex-col gap-2 min-[520px]:w-auto min-[520px]:flex-row min-[520px]:flex-wrap min-[520px]:items-center min-[520px]:justify-end">
          <RouterLink to="/app" class="inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-200 bg-white px-4 py-2 text-center text-sm font-medium transition hover:border-zinc-300 dark:border-white/10 dark:bg-white/[0.04]">
            {{ t('account.openWorkspace') }}
          </RouterLink>
          <RouterLink to="/enterprise?intent=upgrade-enterprise" class="inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-200 bg-white px-4 py-2 text-center text-sm font-medium transition hover:border-zinc-300 dark:border-white/10 dark:bg-white/[0.04]">
            {{ t('account.upgrade') }}
          </RouterLink>
          <button
            type="button"
            class="inline-flex min-h-11 items-center justify-center rounded-full bg-zinc-950 px-4 py-2 text-center text-sm font-semibold text-white dark:bg-white dark:text-zinc-950"
            @click="handleSignOut"
          >
            {{ t('account.signOut') }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="mt-8 rounded-3xl border border-zinc-200 bg-white p-6 text-sm text-zinc-500 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-400">
        {{ t('account.loading') }}
      </div>

      <div v-else class="mt-8 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <section class="space-y-6">
          <div class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.profile') }}</p>
                <h2 class="mt-3 break-words text-xl font-semibold min-[375px]:text-2xl">{{ me?.name || '-' }}</h2>
                <p class="mt-2 break-all text-sm text-zinc-600 dark:text-zinc-300 sm:break-words">{{ me?.email || '-' }}</p>
              </div>
              <div class="w-full shrink-0 rounded-2xl bg-zinc-100 p-4 text-left sm:w-auto sm:min-w-[10rem] sm:text-right dark:bg-white/[0.06]">
                <p class="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">{{ t('account.plan.title') }}</p>
                <p class="mt-2 text-lg font-semibold">{{ plan?.label || '-' }}</p>
                <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{{ plan?.plan || '-' }}</p>
              </div>
            </div>

            <div class="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <article
                v-for="item in usageCards"
                :key="item.label"
                class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]"
              >
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">{{ item.label }}</p>
                <p class="mt-3 text-2xl font-semibold">{{ item.value }}</p>
                <p class="mt-2 text-sm text-zinc-500 dark:text-zinc-400">{{ item.helper }}</p>
              </article>
            </div>
          </div>

          <div class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
              <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.byok.title') }}</p>
                <p class="mt-2 text-sm text-zinc-600 dark:text-zinc-300">{{ t('account.byok.subtitle') }}</p>
              </div>
              <span class="inline-flex shrink-0 self-start rounded-full px-3 py-1 text-xs font-semibold" :class="byokBadgeClass">
                {{ plan?.byok?.enabled ? t('account.byok.enabled') : t('account.byok.disabled') }}
              </span>
            </div>

            <form class="mt-6 grid gap-4 md:grid-cols-2" @submit.prevent="saveByok">
              <label class="block md:col-span-2">
                <span class="mb-2 block text-sm font-medium">{{ t('account.byok.apiKey') }}</span>
                <input
                  v-model="byokForm.apiKey"
                  type="password"
                  :placeholder="t('account.byok.apiKeyPlaceholder')"
                  class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10"
                />
              </label>
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('account.byok.apiBase') }}</span>
                <input v-model="byokForm.apiBase" type="text" class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10" />
              </label>
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('account.byok.model') }}</span>
                <input v-model="byokForm.model" type="text" class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10" />
              </label>
              <div class="md:col-span-2 flex items-center gap-3">
                <button type="submit" class="rounded-full bg-zinc-950 px-5 py-2.5 text-sm font-semibold text-white dark:bg-white dark:text-zinc-950">
                  {{ t('account.byok.save') }}
                </button>
                <p v-if="saved" class="text-sm text-emerald-600 dark:text-emerald-300">{{ t('account.byok.saved') }}</p>
              </div>
            </form>
          </div>

          <MemoryManagerSection />

          <div class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <div>
              <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.team.title') }}</p>
              <p class="mt-2 text-sm text-zinc-600 dark:text-zinc-300">{{ t('account.team.subtitle') }}</p>
            </div>

            <div class="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('account.team.orgName') }}</span>
                <input v-model="teamForm.organizationName" type="text" class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10" />
              </label>
              <div class="flex items-end">
                <button type="button" class="rounded-full bg-zinc-950 px-5 py-2.5 text-sm font-semibold text-white dark:bg-white dark:text-zinc-950" @click="saveTeamName">
                  {{ t('account.team.rename') }}
                </button>
              </div>
            </div>

            <div class="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('account.team.knowledgeScope') }}</span>
                <select v-model="teamForm.scope" class="form-select">
                  <option value="private">{{ t('account.team.private') }}</option>
                  <option value="organization">{{ t('account.team.organization') }}</option>
                </select>
              </label>
              <div class="flex items-end">
                <button type="button" class="rounded-full border border-zinc-200 bg-white px-5 py-2.5 text-sm font-semibold dark:border-white/10 dark:bg-white/[0.04]" @click="saveKnowledgeScope">
                  {{ t('account.team.saveScope') }}
                </button>
              </div>
            </div>

            <div class="mt-6">
              <p class="text-sm font-semibold text-zinc-600 dark:text-zinc-300">{{ t('account.team.members') }}</p>
              <div class="mt-3 space-y-2">
                <article
                  v-for="member in team?.members || []"
                  :key="member.userId"
                  class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]"
                >
                  <div class="flex flex-col gap-2 min-[380px]:flex-row min-[380px]:items-center min-[380px]:justify-between min-[380px]:gap-3">
                    <div class="min-w-0">
                      <p class="break-words text-sm font-semibold">{{ member.name }}</p>
                      <p class="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{{ member.email }}</p>
                    </div>
                    <span class="rounded-full bg-zinc-200 px-2.5 py-1 text-[11px] font-medium text-zinc-700 dark:bg-white/[0.08] dark:text-zinc-300">
                      {{ member.role }}
                    </span>
                  </div>
                </article>
              </div>
            </div>

            <div class="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('account.team.memberName') }}</span>
                <input v-model="teamForm.memberName" type="text" class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10" />
              </label>
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('account.team.memberEmail') }}</span>
                <input v-model="teamForm.memberEmail" type="email" class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10" />
              </label>
              <label class="block">
                <span class="mb-2 block text-sm font-medium">{{ t('account.team.memberRole') }}</span>
                <select v-model="teamForm.memberRole" class="form-select">
                  <option value="owner">{{ t('account.team.owner') }}</option>
                  <option value="editor">{{ t('account.team.editor') }}</option>
                  <option value="viewer">{{ t('account.team.viewer') }}</option>
                </select>
              </label>
            </div>
            <div class="mt-4">
              <button type="button" class="rounded-full border border-zinc-200 bg-white px-5 py-2.5 text-sm font-semibold dark:border-white/10 dark:bg-white/[0.04]" @click="inviteMember">
                {{ t('account.team.addMember') }}
              </button>
            </div>
          </div>
        </section>

        <section class="space-y-6">
          <div class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.plan.title') }}</p>
            <ul class="mt-5 space-y-3 text-sm text-zinc-600 dark:text-zinc-300">
              <li>{{ t('account.plan.tasks') }}: {{ plan?.usage?.tasks ?? 0 }} / {{ formatPlanLimit(plan?.limits?.tasks) }}</li>
              <li>{{ t('account.plan.tokens') }}: {{ plan?.usage?.tokens ?? 0 }}</li>
              <li>{{ t('account.plan.attachments') }}: {{ plan?.usage?.attachments ?? 0 }} / {{ formatPlanLimit(plan?.limits?.attachments) }}</li>
            </ul>
          </div>

          <div class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.opsSnapshot') }}</p>
            <div class="mt-5 grid gap-3">
              <article class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">{{ t('account.opsCards.calls') }}</p>
                <p class="mt-3 text-xl font-semibold">{{ totalCalls }}</p>
              </article>
              <article class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">{{ t('account.opsCards.models') }}</p>
                <p class="mt-3 text-xl font-semibold">{{ activeModelCount }}</p>
              </article>
              <article class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">{{ t('account.opsCards.byok') }}</p>
                <p class="mt-3 text-xl font-semibold">{{ plan?.byok?.enabled ? t('account.byok.enabled') : t('account.byok.disabled') }}</p>
              </article>
            </div>
          </div>

          <div class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
            <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.usageBreakdown') }}</p>
            <div class="mt-5 space-y-3">
              <article
                v-for="item in modelRows"
                :key="item.model"
                class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]"
              >
                <div class="flex items-center justify-between gap-3">
                  <p class="text-sm font-semibold">{{ item.model }}</p>
                  <p class="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    {{ t('account.usage.callsWithCount', { n: item.calls }) }}
                  </p>
                </div>
                <p class="mt-3 text-sm text-zinc-600 dark:text-zinc-300">
                  {{ t('account.usage.tokensWithCount', { n: item.tokens }) }}
                </p>
                <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">${{ item.cost.toFixed(4) }}</p>
              </article>
              <p v-if="modelRows.length === 0" class="text-sm text-zinc-500 dark:text-zinc-400">{{ t('account.emptyUsage') }}</p>
            </div>
          </div>

          <div
            v-if="isPlatformAdmin"
            class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]"
          >
            <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.adminOverview') }}</p>
            <div class="mt-5 grid gap-3 sm:grid-cols-2">
              <article
                v-for="item in adminCards"
                :key="item.label"
                class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]"
              >
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">{{ item.label }}</p>
                <p class="mt-3 text-xl font-semibold">{{ item.value }}</p>
              </article>
            </div>
            <div class="mt-5">
              <p class="text-sm font-semibold text-zinc-600 dark:text-zinc-300">{{ t('account.heavyUsers') }}</p>
              <div v-if="heavyUsers.length" class="mt-3 space-y-2">
                <article
                  v-for="item in heavyUsers"
                  :key="item.userId"
                  class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]"
                >
                  <div class="flex items-center justify-between gap-3">
                    <p class="truncate text-sm font-semibold">{{ item.email }}</p>
                    <span class="rounded-full bg-zinc-200 px-2.5 py-1 text-[11px] font-medium text-zinc-700 dark:bg-white/[0.08] dark:text-zinc-300">
                      {{ item.plan }}
                    </span>
                  </div>
                  <p class="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                    {{
                      t('account.usage.heavyUserLine', {
                        tokens: item.tokens,
                        messages: item.messages,
                      })
                    }}
                  </p>
                </article>
              </div>
              <p v-else class="mt-3 text-sm text-zinc-500 dark:text-zinc-400">{{ t('account.noHeavyUsers') }}</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

import MemoryManagerSection from '../components/MemoryManagerSection.vue'
import { useAccountPage } from '../composables/useAccountPage'

const {
  activeModelCount,
  adminCards,
  byokBadgeClass,
  byokForm,
  formatPlanLimit,
  handleSignOut,
  heavyUsers,
  inviteMember,
  isPlatformAdmin,
  loading,
  me,
  modelRows,
  plan,
  saveByok,
  saved,
  saveKnowledgeScope,
  saveTeamName,
  t,
  team,
  teamForm,
  totalCalls,
  usageCards,
} = useAccountPage()
</script>
