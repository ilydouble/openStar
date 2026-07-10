import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiError } from '../../../../shared/infrastructure/http'
import { authApplication } from '../../composition'

interface AuthFormModel {
  name: string
  email: string
  verificationCode: string
}

interface FeatureCard {
  title: string
  body: string
}

/** Manage authentication form state and route transitions for the auth page. */
export function useAuthForm() {
  const { t, tm } = useI18n()
  const translateMessage = tm as unknown as (key: string) => unknown
  const router = useRouter()
  const isLoginMode = ref(false)
  const step = ref<1 | 2>(1)
  const form = reactive<AuthFormModel>({ name: '', email: '', verificationCode: '' })
  const submitting = ref(false)
  const sending = ref(false)
  const codeSent = ref(false)
  const error = ref('')
  const resendCooldown = ref(0)
  let cooldownTimer: ReturnType<typeof setInterval> | undefined

  const featureCards = computed<FeatureCard[]>(() => {
    const raw = translateMessage('auth.features')
    return Array.isArray(raw) ? raw.filter(isFeatureCard) : []
  })

  /** Stop any active resend countdown timer. */
  function stopCooldown(): void {
    if (cooldownTimer !== undefined) clearInterval(cooldownTimer)
    cooldownTimer = undefined
  }

  /** Start the verification-code resend countdown. */
  function startCooldown(seconds = 60): void {
    stopCooldown()
    resendCooldown.value = seconds
    cooldownTimer = setInterval(() => {
      resendCooldown.value -= 1
      if (resendCooldown.value <= 0) stopCooldown()
    }, 1000)
  }

  /** Return the form to the address-entry step. */
  function resetStep(): void {
    step.value = 1
    form.verificationCode = ''
    codeSent.value = false
    error.value = ''
    stopCooldown()
  }

  /** Request a verification code for the current login or registration mode. */
  async function sendCode(): Promise<void> {
    if (sending.value || (!isLoginMode.value && !form.name.trim()) || !form.email) return
    sending.value = true
    error.value = ''
    try {
      await authApplication.sendVerificationCode({
        email: form.email,
        purpose: isLoginMode.value ? 'login' : 'register',
      })
      step.value = 2
      codeSent.value = true
      startCooldown()
    } catch (cause: unknown) {
      error.value = !isLoginMode.value && cause instanceof ApiError && cause.status === 400
        ? t('auth.emailAlreadyRegistered')
        : readErrorMessage(cause, t('auth.failed'))
    } finally {
      sending.value = false
    }
  }

  /** Submit the current verification code and enter the workspace on success. */
  async function submit(): Promise<void> {
    if (submitting.value) return
    submitting.value = true
    error.value = ''
    try {
      if (isLoginMode.value) {
        await authApplication.emailLogin({
          email: form.email,
          verificationCode: form.verificationCode,
        })
      } else {
        await authApplication.registerTrial({
          name: form.name,
          email: form.email,
          verificationCode: form.verificationCode,
        })
      }
      await router.push({ name: 'workspace' })
    } catch (cause: unknown) {
      error.value = readErrorMessage(cause, t('auth.failed'))
    } finally {
      submitting.value = false
    }
  }

  watch(isLoginMode, resetStep)
  onBeforeUnmount(stopCooldown)

  return {
    codeSent,
    error,
    featureCards,
    form,
    isLoginMode,
    resendCooldown,
    resetStep,
    sendCode,
    sending,
    step,
    submit,
    submitting,
    t,
  }
}

/** Narrow locale message entries to the feature-card view model. */
function isFeatureCard(value: unknown): value is FeatureCard {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const candidate = value as Partial<FeatureCard>
  return typeof candidate.title === 'string' && typeof candidate.body === 'string'
}

/** Convert an unknown failure into safe user-facing text. */
function readErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}
