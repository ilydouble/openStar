import { computed, onActivated, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { authApplication } from '../../../auth'
import { accountApplication } from '../../composition'
import type {
  AccountPlan,
  AccountProfile,
  AccountTeam,
  AdminOverview,
  KnowledgeScope,
  TeamMemberRole,
} from '../../domain/models/account'

interface LoadAccountOptions {
  silent?: boolean
}

interface ByokForm {
  apiKey: string
  apiBase: string
  model: string
}

interface TeamForm {
  organizationName: string
  scope: KnowledgeScope
  memberName: string
  memberEmail: string
  memberRole: TeamMemberRole
}

const PLAN_POLL_MS = 10_000

/** Manage account-page data loading, polling, forms, and commands. */
export function useAccountPage() {
  const { t } = useI18n()
  const router = useRouter()
  const loading = ref(true)
  const profile = ref<AccountProfile | null>(null)
  const plan = ref<AccountPlan | null>(null)
  const adminOverview = ref<AdminOverview | null>(null)
  const team = ref<AccountTeam | null>(null)
  const saved = ref(false)
  const byokForm = reactive<ByokForm>({ apiKey: '', apiBase: '', model: '' })
  const teamForm = reactive<TeamForm>({
    organizationName: '',
    scope: 'organization',
    memberName: '',
    memberEmail: '',
    memberRole: 'viewer',
  })
  let planPollTimer: ReturnType<typeof setInterval> | undefined

  const planUsage = computed(() => plan.value?.usage)
  const usageCards = computed(() => {
    const usage = planUsage.value
    const tokenCount = usage?.tokens || 0
    const estimatedCost = usage?.estimatedCost ?? estimatedCostFromTokenCount(tokenCount)
    return [
      { label: t('account.cards.totalTokens'), value: tokenCount, helper: t('account.plan.tokens') },
      {
        label: t('account.cards.totalCost'),
        value: `$${estimatedCost.toFixed(4)}`,
        helper: t('account.cards.estimated'),
      },
      { label: t('account.cards.tasks'), value: usage?.tasks || 0, helper: t('account.plan.tasks') },
      {
        label: t('account.cards.attachments'),
        value: usage?.attachments || 0,
        helper: t('account.plan.attachments'),
      },
    ]
  })
  const modelRows = computed(() =>
    Object.entries(plan.value?.byModel || {}).map(([model, stats]) => ({ model, ...stats })),
  )
  const totalCalls = computed(() => planUsage.value?.modelCalls || 0)
  const activeModelCount = computed(() => planUsage.value?.activeModels || 0)
  const adminCards = computed(() => {
    const users = adminOverview.value?.users
    const usage = adminOverview.value?.usage
    const leads = adminOverview.value?.leads
    return [
      { label: t('account.adminCards.users'), value: users?.total || 0 },
      { label: t('account.adminCards.active'), value: users?.active7d || 0 },
      { label: t('account.adminCards.trials'), value: users?.newTrials7d || 0 },
      { label: t('account.adminCards.leads'), value: leads?.total || 0 },
      {
        label: t('account.adminCards.cost'),
        value: `$${Number(usage?.totalCost || 0).toFixed(4)}`,
      },
    ]
  })
  const heavyUsers = computed(() => adminOverview.value?.heavyUsers || [])
  const isPlatformAdmin = computed(() => profile.value?.roles.includes('admin') || false)
  const byokBadgeClass = computed(() =>
    plan.value?.byok.enabled
      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
      : 'bg-zinc-100 text-zinc-600 dark:bg-white/[0.06] dark:text-zinc-300',
  )

  /** Load the account aggregate and synchronize editable form state. */
  async function loadAccount(options: LoadAccountOptions = {}): Promise<void> {
    if (!options.silent) loading.value = true
    try {
      const overview = await accountApplication.loadOverview()
      profile.value = overview.profile
      plan.value = overview.plan
      adminOverview.value = overview.adminOverview
      team.value = overview.team
      byokForm.apiBase = overview.plan.byok.apiBase
      byokForm.model = overview.plan.byok.model
      teamForm.organizationName = overview.team?.organization.name || ''
      teamForm.scope = overview.team?.organization.knowledgeScope || 'organization'
    } finally {
      if (!options.silent) loading.value = false
    }
  }

  /** Start periodic plan refresh while the page is active. */
  function startPlanPolling(): void {
    stopPlanPolling()
    planPollTimer = setInterval(() => {
      if (document.visibilityState === 'visible') {
        void loadAccount({ silent: true }).catch(() => undefined)
      }
    }, PLAN_POLL_MS)
  }

  /** Stop periodic account refresh. */
  function stopPlanPolling(): void {
    if (planPollTimer !== undefined) clearInterval(planPollTimer)
    planPollTimer = undefined
  }

  /** Refresh account state when the browser tab becomes visible. */
  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      void loadAccount({ silent: true }).catch(() => undefined)
    }
  }

  /** Persist BYOK settings and replace the plan summary returned by the backend. */
  async function saveByok(): Promise<void> {
    saved.value = false
    plan.value = await accountApplication.saveByok({
      apiBase: byokForm.apiBase,
      model: byokForm.model,
      ...(byokForm.apiKey.trim() ? { apiKey: byokForm.apiKey.trim() } : {}),
    })
    byokForm.apiKey = ''
    saved.value = true
  }

  /** Persist a new organization name. */
  async function saveTeamName(): Promise<void> {
    team.value = await accountApplication.renameTeam(teamForm.organizationName)
  }

  /** Persist the selected organization knowledge scope. */
  async function saveKnowledgeScope(): Promise<void> {
    team.value = await accountApplication.updateKnowledgeScope(teamForm.scope)
  }

  /** Invite one member and replace the refreshed team aggregate. */
  async function inviteMember(): Promise<void> {
    if (!teamForm.memberName || !teamForm.memberEmail) return
    team.value = await accountApplication.inviteTeamMember({
      name: teamForm.memberName,
      email: teamForm.memberEmail,
      role: teamForm.memberRole,
    })
    teamForm.memberName = ''
    teamForm.memberEmail = ''
    teamForm.memberRole = 'viewer'
  }

  /** Clear authentication and return to the auth page. */
  async function handleSignOut(): Promise<void> {
    authApplication.signOut()
    await router.push({ name: 'auth' })
  }

  onMounted(async () => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
    await loadAccount()
    startPlanPolling()
  })
  onActivated(async () => {
    await loadAccount({ silent: true })
    startPlanPolling()
  })
  onUnmounted(() => {
    stopPlanPolling()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  return {
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
    me: profile,
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
  }
}

/** Render a plan quota limit, using infinity when the backend marks it unlimited. */
function formatPlanLimit(value: number | null | undefined): string | number {
  return value == null ? '∞' : value
}

/** Mirror backend estimated-cost fallback for older plan payloads. */
function estimatedCostFromTokenCount(tokenCount: number): number {
  return Math.round((tokenCount / 1_000_000) * 2 * 1_000_000) / 1_000_000
}
