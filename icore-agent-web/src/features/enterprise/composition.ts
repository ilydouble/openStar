import { captureEnterpriseLead } from './application/use-cases/captureEnterpriseLead'
import type { EnterpriseLeadCommand } from './domain/models/lead'
import { HttpLeadRepository } from './infrastructure/http/leadApi'

const leadRepository = new HttpLeadRepository()

export const enterpriseApplication = {
  captureLead: (command: EnterpriseLeadCommand) =>
    captureEnterpriseLead(leadRepository, command),
}
