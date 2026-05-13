import { buildAuthHeaders, clearSession, setSession } from '../auth/session.js'

const BASE = '/api/v1/account'

async function parseJson(resp) {
  const payload = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    throw new Error(payload.detail || payload.message || `HTTP ${resp.status}`)
  }
  return payload
}

export async function sendVerificationCode({ email }) {
  const resp = await fetch(`${BASE}/send-verification-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  return parseJson(resp)
}

export async function registerTrial({ name, email, verification_code }) {
  const resp = await fetch(`${BASE}/register-trial`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, verification_code }),
  })
  const payload = await parseJson(resp)
  setSession(payload.access_token, payload.user)
  return payload
}

export async function emailLogin({ email, verification_code }) {
  const resp = await fetch(`${BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, verification_code }),
  })
  const payload = await parseJson(resp)
  setSession(payload.access_token, payload.user)
  return payload
}

export async function captureLead(payload) {
  const resp = await fetch(`${BASE}/leads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseJson(resp)
}

export async function fetchMe() {
  const resp = await fetch(`${BASE}/me`, {
    headers: buildAuthHeaders(),
  })
  return parseJson(resp)
}

export async function fetchPlan() {
  const resp = await fetch(`${BASE}/billing/plan`, {
    headers: buildAuthHeaders(),
  })
  return parseJson(resp)
}

export async function fetchUsageSummary() {
  const resp = await fetch(`${BASE}/usage/summary`, {
    headers: buildAuthHeaders(),
  })
  return parseJson(resp)
}

export async function fetchAdminOverview() {
  const resp = await fetch(`${BASE}/admin/overview`, {
    headers: buildAuthHeaders(),
  })
  return parseJson(resp)
}

export async function fetchProjects() {
  const resp = await fetch(`${BASE}/projects`, {
    headers: buildAuthHeaders(),
  })
  return parseJson(resp)
}

export async function syncProject(payload) {
  const resp = await fetch(`${BASE}/projects/sync`, {
    method: 'POST',
    headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return parseJson(resp)
}

export async function fetchTeam() {
  const resp = await fetch(`${BASE}/team`, {
    headers: buildAuthHeaders(),
  })
  return parseJson(resp)
}

export async function renameTeam(payload) {
  const resp = await fetch(`${BASE}/team/rename`, {
    method: 'POST',
    headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return parseJson(resp)
}

export async function addTeamMember(payload) {
  const resp = await fetch(`${BASE}/team/members`, {
    method: 'POST',
    headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return parseJson(resp)
}

export async function updateKnowledgeScope(payload) {
  const resp = await fetch(`${BASE}/team/knowledge-scope`, {
    method: 'POST',
    headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return parseJson(resp)
}

export async function updateByok(payload) {
  const resp = await fetch(`${BASE}/billing/byok`, {
    method: 'POST',
    headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  return parseJson(resp)
}

export function signOut() {
  clearSession()
}
