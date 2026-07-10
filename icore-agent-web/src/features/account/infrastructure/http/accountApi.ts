import { apiClient } from '../../../../shared/infrastructure/http'
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
} from '../../domain/models/account'
import type { AccountRepository } from '../../domain/repositories/accountRepository'
import type {
  AccountMemoryDto,
  AccountPlanDto,
  AccountProfileDto,
  AccountProjectDto,
  AccountTeamDto,
  AccountUsageSummaryDto,
  AdminOverviewDto,
  ByokDto,
  MemoryFactDto,
  ProjectListDto,
} from './accountDtos'
import {
  mapAccountMemory,
  mapAccountPlan,
  mapAccountProfile,
  mapAccountProject,
  mapAccountTeam,
  mapAdminOverview,
  mapByok,
  mapMemoryFact,
  mapProjectList,
  mapUsageSummary,
} from './accountMapper'

const BASE = '/account'

/** Axios-backed implementation of the account repository port. */
export class HttpAccountRepository implements AccountRepository {
  /** Fetch the current account profile. */
  async getProfile(): Promise<AccountProfile> {
    return mapAccountProfile(await apiClient.get<AccountProfileDto>(`${BASE}/me`))
  }

  /** Fetch the current plan, quota, and BYOK settings. */
  async getPlan(): Promise<AccountPlan> {
    return mapAccountPlan(await apiClient.get<AccountPlanDto>(`${BASE}/billing/plan`))
  }

  /** Fetch standalone account usage analytics. */
  async getUsageSummary(): Promise<AccountUsageSummary> {
    return mapUsageSummary(await apiClient.get<AccountUsageSummaryDto>(`${BASE}/usage/summary`))
  }

  /** Fetch platform-wide metrics for an authorized administrator. */
  async getAdminOverview(): Promise<AdminOverview> {
    return mapAdminOverview(await apiClient.get<AdminOverviewDto>(`${BASE}/admin/overview`))
  }

  /** Fetch projects linked to the current account. */
  async getProjects(): Promise<ProjectList> {
    return mapProjectList(await apiClient.get<ProjectListDto>(`${BASE}/projects`))
  }

  /** Synchronize one workspace session into an account project. */
  async syncProject(command: SyncProjectCommand): Promise<AccountProject> {
    const dto = await apiClient.post<AccountProjectDto>(`${BASE}/projects/sync`, {
      project_id: command.projectId,
      project_title: command.projectTitle,
      scenario_id: command.scenarioId,
      session_id: command.sessionId,
      session_title: command.sessionTitle,
      session_subtitle: command.sessionSubtitle,
      attachment_count: command.attachmentCount,
    })
    return mapAccountProject(dto)
  }

  /** Fetch organization settings and members. */
  async getTeam(): Promise<AccountTeam> {
    return mapAccountTeam(await apiClient.get<AccountTeamDto>(`${BASE}/team`))
  }

  /** Rename the current account organization. */
  async renameTeam(organizationName: string): Promise<AccountTeam> {
    const dto = await apiClient.post<AccountTeamDto>(`${BASE}/team/rename`, {
      organization_name: organizationName,
    })
    return mapAccountTeam(dto)
  }

  /** Invite one member to the current organization. */
  async addTeamMember(command: AddTeamMemberCommand): Promise<void> {
    await apiClient.post(`${BASE}/team/members`, command)
  }

  /** Update the organization's knowledge visibility scope. */
  async updateKnowledgeScope(scope: KnowledgeScope): Promise<AccountTeam> {
    const dto = await apiClient.post<AccountTeamDto>(`${BASE}/team/knowledge-scope`, { scope })
    return mapAccountTeam(dto)
  }

  /** Update BYOK settings and return the resulting plan summary. */
  async updateByok(command: ByokCommand): Promise<ByokSettings> {
    const dto = await apiClient.post<ByokDto>(`${BASE}/billing/byok`, {
      api_base: command.apiBase,
      model: command.model,
      ...(command.apiKey ? { api_key: command.apiKey } : {}),
    })
    return mapByok(dto)
  }

  /** Fetch the active durable memory facts for the account. */
  async getMemory(): Promise<AccountMemory> {
    return mapAccountMemory(await apiClient.get<AccountMemoryDto>(`${BASE}/memory`))
  }

  /** Update one durable memory fact. */
  async updateMemoryFact(factId: number, value: string): Promise<MemoryFact> {
    const dto = await apiClient.put<MemoryFactDto>(`${BASE}/memory/facts/${factId}`, { value })
    return mapMemoryFact(dto)
  }

  /** Delete one durable memory fact. */
  async deleteMemoryFact(factId: number): Promise<void> {
    await apiClient.delete(`${BASE}/memory/facts/${factId}`)
  }
}
