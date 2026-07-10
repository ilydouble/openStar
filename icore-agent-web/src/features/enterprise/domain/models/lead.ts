export type LeadIntent = 'demo' | 'enterprise' | 'upgrade-team' | 'upgrade-enterprise'

export interface EnterpriseLeadCommand {
  name: string
  email: string
  company: string
  teamSize: string
  useCase: string
  needsByok: boolean
  needsPrivateDeploy: boolean
  source: string
  intent: LeadIntent
}

export interface EnterpriseLead extends EnterpriseLeadCommand {
  id: string
  createdAt: number
}
