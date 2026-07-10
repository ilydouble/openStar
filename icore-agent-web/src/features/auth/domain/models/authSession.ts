export interface AuthUser {
  id: string
  name: string
  email: string
  plan: string
  planLabel: string
  organizationId: string
  organizationName: string
  roles: string[]
  byok: Record<string, unknown>
  usage: Record<string, unknown>
  createdAt: number
  updatedAt: number
}

export interface AuthSession {
  accessToken: string
  tokenType: string
  user: AuthUser | null
}

export type VerificationPurpose = 'login' | 'register'

export interface VerificationCodeCommand {
  email: string
  purpose?: VerificationPurpose
}

export interface RegisterTrialCommand {
  name: string
  email: string
  verificationCode: string
}

export interface EmailLoginCommand {
  email: string
  verificationCode: string
}

export interface VerificationCodeResult {
  success: boolean
  message: string
}
