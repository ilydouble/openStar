export { enterpriseApplication } from './composition'
export type { EnterpriseLeadCommand, LeadIntent } from './domain/models/lead'

/** Load the enterprise contact page through its public feature boundary. */
export function loadEnterprisePage() {
  return import('./presentation/pages/EnterprisePage.vue')
}
