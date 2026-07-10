export interface AccountProfile {
  id: string
  name: string
  email: string
  plan: string
  planLabel: string
  organizationId: string
  organizationName: string
  roles: string[]
  byok: ByokSettings
  usage: Record<string, unknown>
  createdAt: number
  updatedAt: number
}

export interface ByokSettings {
  enabled: boolean
  apiKey: string
  apiBase: string
  model: string
}

export interface ByokCommand {
  apiKey?: string
  apiBase: string
  model: string
}

export interface PlanLimits {
  tasks: number | null
  attachments: number | null
}

export interface PlanUsage {
  tasks: number
  tokens: number
  attachments: number
  estimatedCost: number
  modelCalls: number
  activeModels: number
}

export interface ModelUsage {
  calls: number
  tokens: number
  cost: number
}

export interface AccountPlan {
  plan: string
  label: string
  limits: PlanLimits
  usage: PlanUsage
  modelsUsed: string[]
  byModel: Record<string, ModelUsage>
  quotaPeriod: {
    start: number
    nextReset: number
  }
  byok: ByokSettings
}

export interface AccountUsageSummary {
  estimatedCost: number
  modelCalls: number
  activeModels: number
  modelsUsed: string[]
  byModel: Record<string, ModelUsage>
}

export interface TeamOrganization {
  id: string
  name: string
  knowledgeScope: KnowledgeScope
}

export type KnowledgeScope = 'private' | 'organization'
export type TeamMemberRole = 'owner' | 'editor' | 'viewer' | string

export interface TeamMember {
  userId: string
  name: string
  email: string
  role: TeamMemberRole
  status: string
  createdAt: number
}

export interface AccountTeam {
  organization: TeamOrganization
  members: TeamMember[]
  currentUserId: string
}

export interface AddTeamMemberCommand {
  name: string
  email: string
  role: TeamMemberRole
}

export interface HeavyUser {
  userId: string
  email: string
  tokens: number
  messages: number
  plan: string
}

export interface AdminOverview {
  users: {
    total: number
    active7d: number
    trial: number
    byokEnabled: number
    newTrials7d: number
  }
  leads: {
    total: number
    enterprise: number
    demo: number
  }
  usage: {
    totalCalls: number
    totalTokens: number
    totalCost: number
    byModel: Record<string, ModelUsage>
  }
  heavyUsers: HeavyUser[]
}

export interface ProjectSession {
  sessionId: string
  title: string
  subtitle: string
  attachmentCount: number
  updatedAt: number
}

export interface AccountProject {
  id: string
  title: string
  scenarioId: string
  updatedAt: number
  ownerUserId: string
  sessionsCount: number
  assetsCount: number
  sessions: ProjectSession[]
}

export interface ProjectList {
  projects: AccountProject[]
  recentSessions: ProjectSession[]
}

export interface SyncProjectCommand {
  projectId: string
  projectTitle: string
  scenarioId: string
  sessionId: string
  sessionTitle: string
  sessionSubtitle: string
  attachmentCount: number
}

export type MemoryCategory = 'personal' | 'work_context' | 'goal' | 'preference' | 'constraint'

export interface MemoryFact {
  id: number
  category: MemoryCategory
  key: string
  value: string
  confidence: number
  salience: number
  source: string
  lastConfirmedAt: number
  updatedAt: number
}

export interface AccountMemory {
  profile: Record<string, unknown>
  facts: MemoryFact[]
}

export interface AccountOverview {
  profile: AccountProfile
  plan: AccountPlan
  adminOverview: AdminOverview | null
  team: AccountTeam | null
}
