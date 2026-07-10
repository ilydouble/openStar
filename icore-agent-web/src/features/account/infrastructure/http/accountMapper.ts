import type {
  AccountMemory,
  AccountPlan,
  AccountProfile,
  AccountProject,
  AccountTeam,
  AccountUsageSummary,
  AdminOverview,
  ByokSettings,
  MemoryCategory,
  MemoryFact,
  ModelUsage,
  ProjectList,
  ProjectSession,
} from '../../domain/models/account'
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
  ModelUsageDto,
  ProjectListDto,
  ProjectSessionDto,
} from './accountDtos'

/** Map account profile transport data into the account domain. */
export function mapAccountProfile(dto: AccountProfileDto): AccountProfile {
  return {
    id: dto.id,
    name: dto.name,
    email: dto.email,
    plan: dto.plan,
    planLabel: dto.plan_label,
    organizationId: dto.organization_id,
    organizationName: dto.organization_name,
    roles: dto.roles,
    byok: mapByok(dto.byok),
    usage: dto.usage,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

/** Map plan and quota transport data into the account domain. */
export function mapAccountPlan(dto: AccountPlanDto): AccountPlan {
  return {
    plan: dto.plan,
    label: dto.label,
    limits: dto.limits,
    usage: {
      tasks: dto.usage.tasks,
      tokens: dto.usage.tokens,
      attachments: dto.usage.attachments,
      estimatedCost: dto.usage.estimated_cost,
      modelCalls: dto.usage.model_calls,
      activeModels: dto.usage.active_models,
    },
    modelsUsed: dto.models_used,
    byModel: mapModelUsageRecord(dto.by_model),
    quotaPeriod: {
      start: dto.quota_period.start,
      nextReset: dto.quota_period.next_reset,
    },
    byok: mapByok(dto.byok),
  }
}

/** Map the standalone usage summary into domain naming. */
export function mapUsageSummary(dto: AccountUsageSummaryDto): AccountUsageSummary {
  return {
    estimatedCost: dto.estimated_cost,
    modelCalls: dto.model_calls,
    activeModels: dto.active_models,
    modelsUsed: dto.models_used,
    byModel: mapModelUsageRecord(dto.by_model),
  }
}

/** Map team organization and member transport data into domain models. */
export function mapAccountTeam(dto: AccountTeamDto): AccountTeam {
  return {
    organization: {
      id: dto.organization.id,
      name: dto.organization.name,
      knowledgeScope: dto.organization.knowledge_scope === 'private' ? 'private' : 'organization',
    },
    members: dto.members.map((member) => ({
      userId: member.user_id,
      name: member.name,
      email: member.email,
      role: member.role,
      status: member.status,
      createdAt: member.created_at,
    })),
    currentUserId: dto.current_user_id,
  }
}

/** Map platform administration metrics into domain naming. */
export function mapAdminOverview(dto: AdminOverviewDto): AdminOverview {
  return {
    users: {
      total: dto.users.total,
      active7d: dto.users.active_7d,
      trial: dto.users.trial,
      byokEnabled: dto.users.byok_enabled,
      newTrials7d: dto.users.new_trials_7d,
    },
    leads: dto.leads,
    usage: {
      totalCalls: dto.usage.total_calls,
      totalTokens: dto.usage.total_tokens,
      totalCost: dto.usage.total_cost,
      byModel: mapModelUsageRecord(dto.usage.by_model),
    },
    heavyUsers: dto.heavy_users.map((user) => ({
      userId: user.user_id,
      email: user.email,
      tokens: user.tokens,
      messages: user.messages,
      plan: user.plan,
    })),
  }
}

/** Map a project list payload into project and recent-session models. */
export function mapProjectList(dto: ProjectListDto): ProjectList {
  return {
    projects: dto.projects.map(mapAccountProject),
    recentSessions: dto.recent_sessions.map(mapProjectSession),
  }
}

/** Map one account project transport record. */
export function mapAccountProject(dto: AccountProjectDto): AccountProject {
  return {
    id: dto.id,
    title: dto.title,
    scenarioId: dto.scenario_id,
    updatedAt: dto.updated_at,
    ownerUserId: dto.owner_user_id,
    sessionsCount: dto.sessions_count,
    assetsCount: dto.assets_count,
    sessions: dto.sessions.map(mapProjectSession),
  }
}

/** Map one project session transport record. */
function mapProjectSession(dto: ProjectSessionDto): ProjectSession {
  return {
    sessionId: dto.session_id,
    title: dto.title,
    subtitle: dto.subtitle,
    attachmentCount: dto.attachment_count,
    updatedAt: dto.updated_at,
  }
}

/** Map durable account memory into domain models. */
export function mapAccountMemory(dto: AccountMemoryDto): AccountMemory {
  return { profile: dto.profile, facts: dto.facts.map(mapMemoryFact) }
}

/** Map one durable memory fact into domain naming. */
export function mapMemoryFact(dto: MemoryFactDto): MemoryFact {
  return {
    id: dto.id,
    category: normalizeMemoryCategory(dto.category),
    key: dto.key,
    value: dto.value,
    confidence: dto.confidence,
    salience: dto.salience,
    source: dto.source,
    lastConfirmedAt: dto.last_confirmed_at,
    updatedAt: dto.updated_at,
  }
}

/** Map BYOK settings while preserving redacted API key values. */
export function mapByok(dto: ByokDto): ByokSettings {
  return {
    enabled: Boolean(dto?.enabled),
    apiKey: dto?.api_key || '',
    apiBase: dto?.api_base || '',
    model: dto?.model || '',
  }
}

/** Map model-indexed usage records without leaking transport names. */
function mapModelUsageRecord(dto: Record<string, ModelUsageDto>): Record<string, ModelUsage> {
  return Object.fromEntries(
    Object.entries(dto || {}).map(([model, usage]) => [model, { ...usage }]),
  )
}

/** Normalize unknown memory categories to the existing preference bucket. */
function normalizeMemoryCategory(category: string): MemoryCategory {
  const supported: MemoryCategory[] = [
    'personal',
    'work_context',
    'goal',
    'preference',
    'constraint',
  ]
  return supported.includes(category as MemoryCategory)
    ? category as MemoryCategory
    : 'preference'
}
