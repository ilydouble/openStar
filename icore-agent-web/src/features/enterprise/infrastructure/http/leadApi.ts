import { apiClient } from '../../../../shared/infrastructure/http'
import type { EnterpriseLead, EnterpriseLeadCommand } from '../../domain/models/lead'
import type { LeadRepository } from '../../domain/repositories/leadRepository'

const BASE = '/account'

interface LeadDto {
  id: string
  name: string
  email: string
  company: string
  team_size: string
  use_case: string
  needs_byok: boolean
  needs_private_deploy: boolean
  source: string
  intent: EnterpriseLead['intent']
  created_at: number
}

interface LeadResponseDto {
  lead: LeadDto
}

/** Axios-backed implementation of the enterprise lead repository. */
export class HttpLeadRepository implements LeadRepository {
  /** Submit one lead and map its transport response into domain naming. */
  async capture(command: EnterpriseLeadCommand): Promise<EnterpriseLead> {
    const response = await apiClient.post<LeadResponseDto>(`${BASE}/leads`, {
      name: command.name,
      email: command.email,
      company: command.company,
      team_size: command.teamSize,
      use_case: command.useCase,
      needs_byok: command.needsByok,
      needs_private_deploy: command.needsPrivateDeploy,
      source: command.source,
      intent: command.intent,
    })
    return mapLead(response.lead)
  }
}

/** Map the backend lead record into the enterprise domain model. */
function mapLead(dto: LeadDto): EnterpriseLead {
  return {
    id: dto.id,
    name: dto.name,
    email: dto.email,
    company: dto.company,
    teamSize: dto.team_size,
    useCase: dto.use_case,
    needsByok: dto.needs_byok,
    needsPrivateDeploy: dto.needs_private_deploy,
    source: dto.source,
    intent: dto.intent,
    createdAt: dto.created_at,
  }
}
