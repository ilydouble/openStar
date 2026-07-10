import type {
  AccountMemory,
  AccountPlan,
  AccountProfile,
  AccountProject,
  AccountTeam,
  AccountUsageSummary,
  AddTeamMemberCommand,
  AdminOverview,
  ByokCommand,
  ByokSettings,
  KnowledgeScope,
  MemoryFact,
  ProjectList,
  SyncProjectCommand,
} from '../models/account'

export interface AccountRepository {
  getProfile(): Promise<AccountProfile>
  getPlan(): Promise<AccountPlan>
  getUsageSummary(): Promise<AccountUsageSummary>
  getAdminOverview(): Promise<AdminOverview>
  getProjects(): Promise<ProjectList>
  syncProject(command: SyncProjectCommand): Promise<AccountProject>
  getTeam(): Promise<AccountTeam>
  renameTeam(organizationName: string): Promise<AccountTeam>
  addTeamMember(command: AddTeamMemberCommand): Promise<void>
  updateKnowledgeScope(scope: KnowledgeScope): Promise<AccountTeam>
  updateByok(command: ByokCommand): Promise<ByokSettings>
  getMemory(): Promise<AccountMemory>
  updateMemoryFact(factId: number, value: string): Promise<MemoryFact>
  deleteMemoryFact(factId: number): Promise<void>
}
