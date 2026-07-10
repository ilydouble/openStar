import { apiClient } from '../../../../shared/infrastructure/http'
import type {
  AuthSession,
  AuthUser,
  EmailLoginCommand,
  RegisterTrialCommand,
  VerificationCodeCommand,
  VerificationCodeResult,
} from '../../domain/models/authSession'
import type { AuthRepository } from '../../domain/repositories/authRepository'
import { authTrace } from '../observability/authTrace'

const BASE = '/account'

interface UserProfileDto {
  id: string
  name: string
  email: string
  plan: string
  plan_label: string
  organization_id: string
  organization_name: string
  roles: string[]
  byok: Record<string, unknown>
  usage: Record<string, unknown>
  created_at: number
  updated_at: number
}

interface AuthSessionDto {
  access_token: string
  token_type: string
  user: UserProfileDto
}

interface VerificationCodeDto {
  success: boolean
  message: string
}

/** Map an account user DTO into the feature's domain model. */
function mapUser(dto: UserProfileDto): AuthUser {
  return {
    id: dto.id,
    name: dto.name,
    email: dto.email,
    plan: dto.plan,
    planLabel: dto.plan_label,
    organizationId: dto.organization_id,
    organizationName: dto.organization_name,
    roles: dto.roles,
    byok: dto.byok,
    usage: dto.usage,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

/** Validate and map an authentication response into a persisted session model. */
function mapSession(dto: AuthSessionDto): AuthSession {
  const accessToken = String(dto?.access_token || '')
  if (!accessToken) throw new Error('Authentication response missing access_token')
  return {
    accessToken,
    tokenType: dto.token_type || 'bearer',
    user: dto.user ? mapUser(dto.user) : null,
  }
}

/** Axios-backed implementation of the authentication repository port. */
export class HttpAuthRepository implements AuthRepository {
  /** Request a verification code for the selected authentication purpose. */
  async sendVerificationCode(command: VerificationCodeCommand): Promise<VerificationCodeResult> {
    return apiClient.post<VerificationCodeDto>(`${BASE}/send-verification-code`, {
      email: command.email,
      purpose: command.purpose || 'register',
    })
  }

  /** Register a trial account and map the backend session response. */
  async registerTrial(command: RegisterTrialCommand): Promise<AuthSession> {
    const dto = await apiClient.post<AuthSessionDto>(`${BASE}/register-trial`, {
      name: command.name,
      email: command.email,
      verification_code: command.verificationCode,
    })
    authTrace('registerTrial response', { tokenPresent: Boolean(dto.access_token) })
    return mapSession(dto)
  }

  /** Log in with an email verification code and map the backend session response. */
  async emailLogin(command: EmailLoginCommand): Promise<AuthSession> {
    const dto = await apiClient.post<AuthSessionDto>(`${BASE}/login`, {
      email: command.email,
      verification_code: command.verificationCode,
    })
    authTrace('emailLogin response', { tokenPresent: Boolean(dto.access_token) })
    return mapSession(dto)
  }
}
