import type {
  AuthSession,
  EmailLoginCommand,
  RegisterTrialCommand,
  VerificationCodeCommand,
  VerificationCodeResult,
} from '../models/authSession'

export interface AuthRepository {
  sendVerificationCode(command: VerificationCodeCommand): Promise<VerificationCodeResult>
  registerTrial(command: RegisterTrialCommand): Promise<AuthSession>
  emailLogin(command: EmailLoginCommand): Promise<AuthSession>
}
