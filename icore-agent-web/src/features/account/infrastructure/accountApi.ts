import { createJsonClient } from '../../../shared/api/client'

const BASE = '/api/v1/account'
const client = createJsonClient()

export type AccountPayload = Record<string, unknown>

/** Submit an enterprise lead request for follow-up. */
export async function captureLead(payload: AccountPayload): Promise<unknown> {
  return client.post(`${BASE}/leads`, payload)
}

/** Fetch the current account profile. */
export async function fetchMe(): Promise<unknown> {
  return client.get(`${BASE}/me`)
}

/** Fetch the current billing plan. */
export async function fetchPlan(): Promise<unknown> {
  return client.get(`${BASE}/billing/plan`)
}

/** Fetch the current usage summary. */
export async function fetchUsageSummary(): Promise<unknown> {
  return client.get(`${BASE}/usage/summary`)
}

/** Fetch account admin overview data. */
export async function fetchAdminOverview(): Promise<unknown> {
  return client.get(`${BASE}/admin/overview`)
}

/** Fetch projects linked to the current account. */
export async function fetchProjects(): Promise<unknown> {
  return client.get(`${BASE}/projects`)
}

/** Sync a project into the current account workspace. */
export async function syncProject(payload: AccountPayload): Promise<unknown> {
  return client.post(`${BASE}/projects/sync`, payload)
}

/** Fetch team settings and members. */
export async function fetchTeam(): Promise<unknown> {
  return client.get(`${BASE}/team`)
}

/** Rename the current account team. */
export async function renameTeam(payload: AccountPayload): Promise<unknown> {
  return client.post(`${BASE}/team/rename`, payload)
}

/** Add one team member to the current account. */
export async function addTeamMember(payload: AccountPayload): Promise<unknown> {
  return client.post(`${BASE}/team/members`, payload)
}

/** Update the team knowledge scope settings. */
export async function updateKnowledgeScope(payload: AccountPayload): Promise<unknown> {
  return client.post(`${BASE}/team/knowledge-scope`, payload)
}

/** Update BYOK billing settings. */
export async function updateByok(payload: AccountPayload): Promise<unknown> {
  return client.post(`${BASE}/billing/byok`, payload)
}

/** Fetch account memory facts. */
export async function fetchMemory(): Promise<unknown> {
  return client.get(`${BASE}/memory`)
}

/** Update one memory fact value. */
export async function updateMemoryFact(factId: string, value: string): Promise<unknown> {
  return client.put(`${BASE}/memory/facts/${factId}`, { value })
}

/** Delete one memory fact. */
export async function deleteMemoryFact(factId: string): Promise<unknown> {
  return client.delete(`${BASE}/memory/facts/${factId}`)
}
