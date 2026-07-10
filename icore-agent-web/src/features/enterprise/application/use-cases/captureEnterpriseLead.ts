import type { EnterpriseLead, EnterpriseLeadCommand } from '../../domain/models/lead'
import type { LeadRepository } from '../../domain/repositories/leadRepository'

/** Normalize and submit one enterprise follow-up request. */
export function captureEnterpriseLead(
  repository: LeadRepository,
  command: EnterpriseLeadCommand,
): Promise<EnterpriseLead> {
  return repository.capture({
    ...command,
    name: command.name.trim(),
    email: command.email.trim().toLowerCase(),
    company: command.company.trim(),
    useCase: command.useCase.trim(),
  })
}
