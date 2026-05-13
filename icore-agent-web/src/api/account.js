import { clearSession, setSession } from '../auth/session.js'
import { createJsonClient } from './client.js'

const BASE = '/api/v1/account'
const client = createJsonClient()

export async function sendVerificationCode({ email }) {
  return client.post(`${BASE}/send-verification-code`, { email })
}

export async function registerTrial({ name, email, verification_code }) {
  const payload = await client.post(`${BASE}/register-trial`, { name, email, verification_code })
  setSession(payload.access_token, payload.user)
  return payload
}

export async function emailLogin({ email, verification_code }) {
  const payload = await client.post(`${BASE}/login`, { email, verification_code })
  setSession(payload.access_token, payload.user)
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
