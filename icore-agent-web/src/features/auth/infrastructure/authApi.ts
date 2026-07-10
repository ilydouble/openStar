import { createJsonClient } from '../../../shared/api/client'
import {
  clearSession,
  peekAccessTokenState,
  setSession,
  type StoredUser,
} from '../application/session'
import { authTrace } from '../application/trace'

const BASE = '/api/v1/account'
const client = createJsonClient()

type UnknownRecord = Record<string, unknown>

export interface VerificationCodeCommand {
  email: string
  purpose?: string
}

export interface RegisterTrialCommand {
  name: string
  email: string
  verification_code: string
}

export interface EmailLoginCommand {
  email: string
  verification_code: string
}

interface AuthSessionEnvelope {
  token: string
  user: StoredUser | null
}

/** Return whether a value is a plain object record. */
function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

/**
 * Normalize login/register JSON into a session token and user profile.
 */
function extractSessionFromAuthResponse(payload: unknown): AuthSessionEnvelope {
  if (!isRecord(payload)) {
    return { token: '', user: null }
  }
  const envelope = isRecord(payload.data) ? payload.data : payload
  const token = envelope.access_token ?? envelope.accessToken ?? envelope.token ?? ''
  const user = envelope.user ?? envelope.userProfile ?? envelope.profile ?? null
  return {
    token: typeof token === 'string' ? token : '',
    user: isRecord(user) ? user : null,
  }
}

/** Send an email verification code for login or trial registration. */
export async function sendVerificationCode({
  email,
  purpose = 'register',
}: VerificationCodeCommand): Promise<unknown> {
  return client.post(`${BASE}/send-verification-code`, { email, purpose })
}

/** Register a trial account and persist the returned session token. */
export async function registerTrial(command: RegisterTrialCommand): Promise<unknown> {
  const payload = await client.post(`${BASE}/register-trial`, command)
  authTrace('registerTrial response shape', {
    topKeys: isRecord(payload) ? Object.keys(payload).slice(0, 24) : typeof payload,
  })
  const { token, user } = extractSessionFromAuthResponse(payload)
  authTrace('registerTrial extracted', {
    tokenLength: token.length,
    tokenHasValue: Boolean(token),
    userKeys: user ? Object.keys(user).slice(0, 12) : null,
  })
  if (!token) {
    const preview =
      typeof payload === 'object' ? JSON.stringify(payload).slice(0, 420) : String(payload).slice(0, 420)
    authTrace('registerTrial MISSING token - payload preview', { preview })
    throw new Error('Registration response missing access_token')
  }
  setSession(token, user)
  peekAccessTokenState('after registerTrial setSession')
  return payload
}

/** Log in with email verification and persist the returned session token. */
export async function emailLogin(command: EmailLoginCommand): Promise<unknown> {
  const payload = await client.post(`${BASE}/login`, command)
  authTrace('emailLogin response shape', {
    topKeys: isRecord(payload) ? Object.keys(payload).slice(0, 24) : typeof payload,
  })
  const { token, user } = extractSessionFromAuthResponse(payload)
  authTrace('emailLogin extracted', {
    tokenLength: token.length,
    tokenHasValue: Boolean(token),
    userKeys: user ? Object.keys(user).slice(0, 12) : null,
  })
  if (!token) {
    const preview =
      typeof payload === 'object' ? JSON.stringify(payload).slice(0, 420) : String(payload).slice(0, 420)
    authTrace('emailLogin MISSING token - payload preview', { preview })
    throw new Error('Login response missing access_token')
  }
  setSession(token, user)
  peekAccessTokenState('after emailLogin setSession')
  return payload
}

/** Clear the current browser session. */
export function signOut(): void {
  clearSession()
}
