import { apiClient } from '../../../shared/api/api-client'

const BASE = '/account'

export type LeadPayload = Record<string, unknown>

/** Submit an enterprise lead request for follow-up. */
export async function captureLead(payload: LeadPayload): Promise<unknown> {
  return apiClient.post(`${BASE}/leads`, payload)
}
