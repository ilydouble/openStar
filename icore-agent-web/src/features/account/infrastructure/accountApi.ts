import { apiClient } from '../../../shared/infrastructure/http'

const BASE = '/account'

export type AccountPayload = Record<string, unknown>

/** Fetch the current account profile. */
export async function fetchMe(): Promise<unknown> {
  return apiClient.get(`${BASE}/me`)
}

/** Fetch the current billing plan. */
export async function fetchPlan(): Promise<unknown> {
  return apiClient.get(`${BASE}/billing/plan`)
}

/** Fetch the current usage summary. */
export async function fetchUsageSummary(): Promise<unknown> {
  return apiClient.get(`${BASE}/usage/summary`)
}

/** Fetch account admin overview data. */
export async function fetchAdminOverview(): Promise<unknown> {
  return apiClient.get(`${BASE}/admin/overview`)
}

/** Fetch projects linked to the current account. */
export async function fetchProjects(): Promise<unknown> {
  return apiClient.get(`${BASE}/projects`)
}

/** Sync a project into the current account workspace. */
export async function syncProject(payload: AccountPayload): Promise<unknown> {
  return apiClient.post(`${BASE}/projects/sync`, payload)
}

/** Fetch team settings and members. */
export async function fetchTeam(): Promise<unknown> {
  return apiClient.get(`${BASE}/team`)
}

/** Rename the current account team. */
export async function renameTeam(payload: AccountPayload): Promise<unknown> {
  return apiClient.post(`${BASE}/team/rename`, payload)
}

/** Add one team member to the current account. */
export async function addTeamMember(payload: AccountPayload): Promise<unknown> {
  return apiClient.post(`${BASE}/team/members`, payload)
}

/** Update the team knowledge scope settings. */
export async function updateKnowledgeScope(payload: AccountPayload): Promise<unknown> {
  return apiClient.post(`${BASE}/team/knowledge-scope`, payload)
}

/** Update BYOK billing settings. */
export async function updateByok(payload: AccountPayload): Promise<unknown> {
  return apiClient.post(`${BASE}/billing/byok`, payload)
}

/** Fetch account memory facts. */
export async function fetchMemory(): Promise<unknown> {
  return apiClient.get(`${BASE}/memory`)
}

/** Update one memory fact value. */
export async function updateMemoryFact(factId: string, value: string): Promise<unknown> {
  return apiClient.put(`${BASE}/memory/facts/${factId}`, { value })
}

/** Delete one memory fact. */
export async function deleteMemoryFact(factId: string): Promise<unknown> {
  return apiClient.delete(`${BASE}/memory/facts/${factId}`)
}
