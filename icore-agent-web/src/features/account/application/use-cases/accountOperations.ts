import type {
  AccountMemory,
  AccountOverview,
  AccountPlan,
  AccountProject,
  AccountTeam,
  AccountUsageSummary,
  AddTeamMemberCommand,
  ByokCommand,
  KnowledgeScope,
  MemoryFact,
  ProjectList,
  SyncProjectCommand,
} from '../../domain/models/account'
import type { AccountRepository } from '../../domain/repositories/accountRepository'

/** Load the account page aggregate, including optional team and administrator data. */
export async function loadAccountOverview(
  repository: AccountRepository,
): Promise<AccountOverview> {
  const [profile, plan] = await Promise.all([repository.getProfile(), repository.getPlan()])
  const [adminOverview, team] = await Promise.all([
    profile.roles.includes('admin')
      ? repository.getAdminOverview().catch(() => null)
      : Promise.resolve(null),
    repository.getTeam().catch(() => null),
  ])
  return { profile, plan, adminOverview, team }
}

/** Save BYOK settings and return the resulting plan summary. */
export async function saveByok(
  repository: AccountRepository,
  command: ByokCommand,
): Promise<AccountPlan> {
  await repository.updateByok(command)
  return repository.getPlan()
}

/** Rename the current organization. */
export function renameTeam(
  repository: AccountRepository,
  organizationName: string,
): Promise<AccountTeam> {
  return repository.renameTeam(organizationName)
}

/** Update the organization's knowledge scope. */
export function updateKnowledgeScope(
  repository: AccountRepository,
  scope: KnowledgeScope,
): Promise<AccountTeam> {
  return repository.updateKnowledgeScope(scope)
}

/** Invite a team member and refresh the team aggregate. */
export async function inviteTeamMember(
  repository: AccountRepository,
  command: AddTeamMemberCommand,
): Promise<AccountTeam> {
  await repository.addTeamMember(command)
  return repository.getTeam()
}

/** Load active account memory facts. */
export function loadAccountMemory(repository: AccountRepository): Promise<AccountMemory> {
  return repository.getMemory()
}

/** Update one account memory fact. */
export function updateAccountMemoryFact(
  repository: AccountRepository,
  factId: number,
  value: string,
): Promise<MemoryFact> {
  return repository.updateMemoryFact(factId, value)
}

/** Delete one account memory fact. */
export function deleteAccountMemoryFact(
  repository: AccountRepository,
  factId: number,
): Promise<void> {
  return repository.deleteMemoryFact(factId)
}

/** Load the plan summary for workspace quota displays. */
export function loadAccountPlan(repository: AccountRepository): Promise<AccountPlan> {
  return repository.getPlan()
}

/** Load standalone usage analytics for future account consumers. */
export function loadAccountUsage(repository: AccountRepository): Promise<AccountUsageSummary> {
  return repository.getUsageSummary()
}

/** Load projects linked to the current workspace account. */
export function loadAccountProjects(repository: AccountRepository): Promise<ProjectList> {
  return repository.getProjects()
}

/** Synchronize one workspace session with an account project. */
export function synchronizeProject(
  repository: AccountRepository,
  command: SyncProjectCommand,
): Promise<AccountProject> {
  return repository.syncProject(command)
}
