import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { enterpriseApplication } from '../../composition'
import type { EnterpriseLeadCommand, LeadIntent } from '../../domain/models/lead'

interface EnterpriseValueCard {
  title: string
  body: string
}

/** Manage enterprise lead form defaults, submission, and feedback. */
export function useEnterpriseLeadForm() {
  const { t, tm } = useI18n()
  const translateMessage = tm as unknown as (key: string) => unknown
  const route = useRoute()
  const plan = readQueryString(route.query.plan)
  const queryIntent = readQueryString(route.query.intent)
  const submitting = ref(false)
  const success = ref(false)
  const error = ref('')
  const form = reactive<EnterpriseLeadCommand>({
    name: '',
    email: '',
    company: '',
    teamSize: plan === 'enterprise' ? '51-200' : '11-50',
    useCase: '',
    needsByok: plan === 'enterprise',
    needsPrivateDeploy: false,
    source: 'enterprise-page',
    intent: resolveLeadIntent(queryIntent, plan),
  })
  const valueCards = computed<EnterpriseValueCard[]>(() => {
    const raw = translateMessage('enterprise.cards')
    return Array.isArray(raw) ? raw.filter(isValueCard) : []
  })

  /** Submit the current lead form through the enterprise application boundary. */
  async function submit(): Promise<void> {
    if (submitting.value) return
    submitting.value = true
    success.value = false
    error.value = ''
    try {
      await enterpriseApplication.captureLead(form)
      success.value = true
    } catch (cause: unknown) {
      error.value = cause instanceof Error && cause.message ? cause.message : t('enterprise.failed')
    } finally {
      submitting.value = false
    }
  }

  return { error, form, submit, submitting, success, t, valueCards }
}

/** Read the first scalar query value. */
function readQueryString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/** Resolve a supported lead intent from route defaults. */
function resolveLeadIntent(intent: string, plan: string): LeadIntent {
  const supported: LeadIntent[] = ['demo', 'enterprise', 'upgrade-team', 'upgrade-enterprise']
  if (supported.includes(intent as LeadIntent)) return intent as LeadIntent
  if (plan === 'team') return 'upgrade-team'
  if (plan === 'enterprise') return 'upgrade-enterprise'
  return 'demo'
}

/** Narrow translated value-card content. */
function isValueCard(value: unknown): value is EnterpriseValueCard {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const card = value as Partial<EnterpriseValueCard>
  return typeof card.title === 'string' && typeof card.body === 'string'
}
