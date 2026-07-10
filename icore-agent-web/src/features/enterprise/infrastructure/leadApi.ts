import { createJsonClient } from '../../../shared/api/client'

const BASE = '/api/v1/account'
const client = createJsonClient()

export type LeadPayload = Record<string, unknown>

/** Submit an enterprise lead request for follow-up. */
export async function captureLead(payload: LeadPayload): Promise<unknown> {
  return client.post(`${BASE}/leads`, payload)
}
