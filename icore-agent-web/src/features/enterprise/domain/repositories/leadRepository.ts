import type { EnterpriseLead, EnterpriseLeadCommand } from '../models/lead'

export interface LeadRepository {
  capture(command: EnterpriseLeadCommand): Promise<EnterpriseLead>
}
