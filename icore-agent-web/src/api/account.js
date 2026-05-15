import { clearSession, peekAccessTokenState, setSession } from '../auth/session.js'
import { authTrace } from '../auth/trace.js'
import { createJsonClient } from './client.js'

const BASE = '/api/v1/account'
const client = createJsonClient()

/**
 * Normalize login/register JSON (direct body or accidental `{ data }` wrappers,
 * camelCase vs snake_case) and return `{ token, user }`.
 *
 * @param {unknown} payload
 * @returns {{ token: string, user?: object|null }}
 */
function extractSessionFromAuthResponse(payload) {
  if (!payload || typeof payload !== 'object') {
    return { token: '', user: null }
  }
  const raw = payload
  const envelope = typeof raw.data === 'object' && raw.data !== null ? raw.data : raw
  const token =
    envelope.access_token ?? envelope.accessToken ?? envelope.token ?? ''
  const user = envelope.user ?? envelope.userProfile ?? envelope.profile ?? null
  return {
    token: typeof token === 'string' ? token : '',
    user,
  }
}

export async function sendVerificationCode({ email }) {
  return client.post(`${BASE}/send-verification-code`, { email })
}

export async function registerTrial({ name, email, verification_code }) {
  const payload = await client.post(`${BASE}/register-trial`, { name, email, verification_code })
  authTrace('registerTrial response shape', {
    topKeys:
      payload && typeof payload === 'object' ? Object.keys(payload).slice(0, 24) : typeof payload,
  })
  const { token, user } = extractSessionFromAuthResponse(payload)
  authTrace('registerTrial extracted', {
    tokenLength: token.length,
    tokenHasValue: Boolean(token),
    userKeys:
      user && typeof user === 'object' ? Object.keys(user).slice(0, 12) : null,
  })
  if (!token) {
    const preview =
      typeof payload === 'object' ? JSON.stringify(payload).slice(0, 420) : String(payload).slice(0, 420)
    authTrace('registerTrial MISSING token — payload preview', { preview })
    throw new Error('Registration response missing access_token')
  }
  setSession(token, user ?? undefined)
  peekAccessTokenState('after registerTrial setSession')
  return payload
}

export async function emailLogin({ email, verification_code }) {
  const payload = await client.post(`${BASE}/login`, { email, verification_code })
  authTrace('emailLogin response shape', {
    topKeys:
      payload && typeof payload === 'object' ? Object.keys(payload).slice(0, 24) : typeof payload,
  })
  const { token, user } = extractSessionFromAuthResponse(payload)
  authTrace('emailLogin extracted', {
    tokenLength: token.length,
    tokenHasValue: Boolean(token),
    userKeys:
      user && typeof user === 'object' ? Object.keys(user).slice(0, 12) : null,
  })
  if (!token) {
    const preview =
      typeof payload === 'object' ? JSON.stringify(payload).slice(0, 420) : String(payload).slice(0, 420)
    authTrace('emailLogin MISSING token — payload preview', { preview })
    throw new Error('Login response missing access_token')
  }
  setSession(token, user ?? undefined)
  peekAccessTokenState('after emailLogin setSession')
  return payload
}

export async function captureLead(payload) {
  return client.post(`${BASE}/leads`, payload)
}

export async function fetchMe() {
  return client.get(`${BASE}/me`)
}

export async function fetchPlan() {
  return client.get(`${BASE}/billing/plan`)
}

export async function fetchUsageSummary() {
  return client.get(`${BASE}/usage/summary`)
}

export async function fetchAdminOverview() {
  return client.get(`${BASE}/admin/overview`)
}

export async function fetchProjects() {
  return client.get(`${BASE}/projects`)
}

export async function syncProject(payload) {
  return client.post(`${BASE}/projects/sync`, payload)
}

export async function fetchTeam() {
  return client.get(`${BASE}/team`)
}

export async function renameTeam(payload) {
  return client.post(`${BASE}/team/rename`, payload)
}

export async function addTeamMember(payload) {
  return client.post(`${BASE}/team/members`, payload)
}

export async function updateKnowledgeScope(payload) {
  return client.post(`${BASE}/team/knowledge-scope`, payload)
}

export async function updateByok(payload) {
  return client.post(`${BASE}/billing/byok`, payload)
}

export function signOut() {
  clearSession()
}
