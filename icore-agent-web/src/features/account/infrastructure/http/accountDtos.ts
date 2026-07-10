export interface ByokDto {
  enabled: boolean
  api_key: string
  api_base: string
  model: string
}

export interface AccountProfileDto {
  id: string
  name: string
  email: string
  plan: string
  plan_label: string
  organization_id: string
  organization_name: string
  roles: string[]
  byok: ByokDto
  usage: Record<string, unknown>
  created_at: number
  updated_at: number
}

export interface ModelUsageDto {
  calls: number
  tokens: number
  cost: number
}

export interface AccountUsageSummaryDto {
  estimated_cost: number
  model_calls: number
  active_models: number
  models_used: string[]
  by_model: Record<string, ModelUsageDto>
}

export interface AccountPlanDto {
  plan: string
  label: string
  limits: { tasks: number | null; attachments: number | null }
  usage: {
    tasks: number
    tokens: number
    attachments: number
    estimated_cost: number
    model_calls: number
    active_models: number
  }
  models_used: string[]
  by_model: Record<string, ModelUsageDto>
  quota_period: { start: number; next_reset: number }
  byok: ByokDto
}

export interface TeamMemberDto {
  user_id: string
  name: string
  email: string
  role: string
  status: string
  created_at: number
}

export interface AccountTeamDto {
  organization: { id: string; name: string; knowledge_scope: string }
  members: TeamMemberDto[]
  current_user_id: string
}

export interface AdminOverviewDto {
  users: {
    total: number
    active_7d: number
    trial: number
    byok_enabled: number
    new_trials_7d: number
  }
  leads: { total: number; enterprise: number; demo: number }
  usage: {
    total_calls: number
    total_tokens: number
    total_cost: number
    by_model: Record<string, ModelUsageDto>
  }
  heavy_users: Array<{
    user_id: string
    email: string
    tokens: number
    messages: number
    plan: string
  }>
}

export interface ProjectSessionDto {
  session_id: string
  title: string
  subtitle: string
  attachment_count: number
  updated_at: number
}

export interface AccountProjectDto {
  id: string
  title: string
  scenario_id: string
  updated_at: number
  owner_user_id: string
  sessions_count: number
  assets_count: number
  sessions: ProjectSessionDto[]
}

export interface ProjectListDto {
  projects: AccountProjectDto[]
  recent_sessions: ProjectSessionDto[]
}

export interface MemoryFactDto {
  id: number
  category: string
  key: string
  value: string
  confidence: number
  salience: number
  source: string
  last_confirmed_at: number
  updated_at: number
}

export interface AccountMemoryDto {
  profile: Record<string, unknown>
  facts: MemoryFactDto[]
}
