<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        @click.self="$emit('dismiss')"
      >
        <div
          class="relative flex w-full max-w-2xl flex-col overflow-hidden rounded-[2rem] border border-zinc-200/80 bg-white shadow-2xl dark:border-white/10 dark:bg-zinc-900"
          @click.stop
        >
          <!-- close button -->
          <button
            type="button"
            class="absolute right-6 top-6 rounded-full p-2 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-950 dark:hover:bg-white/10 dark:hover:text-white"
            :aria-label="t('quotaModal.dismiss')"
            @click="$emit('dismiss')"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <div class="p-8 sm:p-10">
            <!-- header -->
            <div class="flex flex-col items-center text-center">
              <div class="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 text-3xl dark:bg-amber-400/10">
                ⚡
              </div>
              <h2 class="mt-4 text-2xl font-semibold tracking-tight text-zinc-950 dark:text-white sm:text-3xl">
                {{ t('quotaModal.title') }}
              </h2>
              <p class="mt-2 max-w-md text-sm leading-6 text-zinc-500 dark:text-zinc-400">
                {{ t('quotaModal.subtitle', { plan: planLabel, limit: taskLimit }) }}
              </p>
            </div>

            <!-- plan cards -->
            <div class="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div
                v-for="plan in plans"
                :key="plan.key"
                class="relative flex flex-col rounded-2xl border p-5 transition-shadow hover:shadow-lg"
                :class="plan.featured
                  ? 'border-violet-400/60 bg-violet-50/60 dark:border-violet-400/30 dark:bg-violet-400/5'
                  : 'border-zinc-200/80 bg-zinc-50/60 dark:border-white/10 dark:bg-white/[0.03]'"
              >
                <!-- badge -->
                <span
                  v-if="plan.badge"
                  class="absolute -top-2.5 left-1/2 -translate-x-1/2 rounded-full px-3 py-0.5 text-[11px] font-semibold"
                  :class="plan.featured
                    ? 'bg-violet-600 text-white'
                    : 'bg-emerald-500 text-white'"
                >
                  {{ plan.badge }}
                </span>

                <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ plan.name }}</p>
                <p class="mt-1 text-xs font-medium text-violet-600 dark:text-violet-400">{{ plan.tasks }}</p>
                <p class="text-xs text-zinc-400 dark:text-zinc-500">{{ plan.price }}</p>
                <p class="mt-2 flex-1 text-xs leading-5 text-zinc-500 dark:text-zinc-400">{{ plan.desc }}</p>

                <button
                  type="button"
                  class="mt-4 w-full rounded-xl py-2 text-sm font-medium transition-colors"
                  :class="plan.featured
                    ? 'bg-violet-600 text-white hover:bg-violet-700'
                    : 'border border-zinc-300/80 bg-white text-zinc-800 hover:bg-zinc-100 dark:border-white/15 dark:bg-white/[0.06] dark:text-zinc-200 dark:hover:bg-white/10'"
                  @click="handleUpgrade(plan)"
                >
                  {{ plan.cta }}
                </button>
              </div>
            </div>

            <!-- footer -->
            <div class="mt-6 flex flex-col items-center gap-2 text-center">
              <button
                type="button"
                class="text-sm text-zinc-400 underline-offset-2 hover:text-zinc-600 hover:underline dark:hover:text-zinc-300"
                @click="$emit('dismiss')"
              >
                {{ t('quotaModal.dismiss') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>


<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

const props = withDefaults(defineProps<{
  show?: boolean
  currentPlan?: string
}>(), { show: false, currentPlan: 'trial' })

const emit = defineEmits<{ dismiss: [] }>()

const { t } = useI18n()
const router = useRouter()

/** Task limit per plan tier — mirrors backend Plan enum for display only. */
const TASK_LIMITS: Record<string, number | null> = {
  trial: 10,
  pro: 200,
  team: 1000,
  premium: 5000,
  byok: null,
}

interface UpgradePlan {
  route: string
}

/** Human-readable plan label shown in the subtitle. */
const planLabel = computed(() => props.currentPlan.charAt(0).toUpperCase() + props.currentPlan.slice(1))

/** Task limit for the user's current plan. */
const taskLimit = computed(() => TASK_LIMITS[props.currentPlan] ?? 10)

const plans = computed(() => [
  {
    key: 'pro',
    name: t('quotaModal.plans.pro.name'),
    tasks: t('quotaModal.plans.pro.tasks'),
    price: t('quotaModal.plans.pro.price'),
    desc: t('quotaModal.plans.pro.desc'),
    cta: t('quotaModal.plans.pro.cta'),
    badge: t('quotaModal.plans.pro.badge'),
    featured: false,
    route: '/account?tab=plan&upgrade=pro',
  },
  {
    key: 'team',
    name: t('quotaModal.plans.team.name'),
    tasks: t('quotaModal.plans.team.tasks'),
    price: t('quotaModal.plans.team.price'),
    desc: t('quotaModal.plans.team.desc'),
    cta: t('quotaModal.plans.team.cta'),
    badge: t('quotaModal.plans.team.badge'),
    featured: true,
    route: '/account?tab=plan&upgrade=team',
  },
  {
    key: 'premium',
    name: t('quotaModal.plans.premium.name'),
    tasks: t('quotaModal.plans.premium.tasks'),
    price: t('quotaModal.plans.premium.price'),
    desc: t('quotaModal.plans.premium.desc'),
    cta: t('quotaModal.plans.premium.cta'),
    badge: t('quotaModal.plans.premium.badge'),
    featured: false,
    route: '/account?tab=plan&upgrade=premium',
  },
  {
    key: 'byok',
    name: t('quotaModal.plans.byok.name'),
    tasks: t('quotaModal.plans.byok.tasks'),
    price: t('quotaModal.plans.byok.price'),
    desc: t('quotaModal.plans.byok.desc'),
    cta: t('quotaModal.plans.byok.cta'),
    badge: t('quotaModal.plans.byok.badge'),
    featured: false,
    route: '/account?tab=byok',
  },
])

/** Navigate to the upgrade page and close the modal. */
function handleUpgrade(plan: UpgradePlan): void {
  emit('dismiss')
  void router.push(plan.route)
}
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
