import type {
  AddTeamMemberCommand,
  ByokCommand,
  KnowledgeScope,
  SyncProjectCommand,
} from '../domain/models/account'
import type { AccountRepository } from '../domain/repositories/accountRepository'
import {
  deleteAccountMemoryFact,
  inviteTeamMember,
  loadAccountMemory,
  loadAccountOverview,
  loadAccountPlan,
  loadAccountProjects,
  loadAccountUsage,
  renameTeam,
  saveByok,
  synchronizeProject,
  updateAccountMemoryFact,
  updateKnowledgeScope,
} from './use-cases/accountOperations'

/** Bind account use cases to one repository implementation. */
export function createAccountApplication(repository: AccountRepository) {
  return {
    loadOverview: () => loadAccountOverview(repository),
    loadPlan: () => loadAccountPlan(repository),
    loadUsage: () => loadAccountUsage(repository),
    loadProjects: () => loadAccountProjects(repository),
    syncProject: (command: SyncProjectCommand) => synchronizeProject(repository, command),
    saveByok: (command: ByokCommand) => saveByok(repository, command),
    renameTeam: (organizationName: string) => renameTeam(repository, organizationName),
    updateKnowledgeScope: (scope: KnowledgeScope) => updateKnowledgeScope(repository, scope),
    inviteTeamMember: (command: AddTeamMemberCommand) => inviteTeamMember(repository, command),
    loadMemory: () => loadAccountMemory(repository),
    updateMemoryFact: (factId: number, value: string) =>
      updateAccountMemoryFact(repository, factId, value),
    deleteMemoryFact: (factId: number) => deleteAccountMemoryFact(repository, factId),
  }
}
