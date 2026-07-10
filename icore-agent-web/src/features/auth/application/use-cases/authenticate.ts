import type {
  AuthSession,
  EmailLoginCommand,
  RegisterTrialCommand,
  VerificationCodeCommand,
  VerificationCodeResult,
} from '../../domain/models/authSession'
import type { AuthRepository } from '../../domain/repositories/authRepository'
import type { SessionRepository } from '../../domain/repositories/sessionRepository'

/** Send a login or registration verification code through the configured auth repository. */
export function sendVerificationCode(
  authRepository: AuthRepository,
  command: VerificationCodeCommand,
): Promise<VerificationCodeResult> {
  return authRepository.sendVerificationCode(command)
}

/** Authenticate an existing user and persist the resulting browser session. */
export async function loginWithEmail(
  authRepository: AuthRepository,
  sessionRepository: SessionRepository,
  command: EmailLoginCommand,
): Promise<AuthSession> {
  const session = await authRepository.emailLogin(command)
  sessionRepository.save(session)
  return session
}

/** Register a trial user and persist the resulting browser session. */
export async function registerTrial(
  authRepository: AuthRepository,
  sessionRepository: SessionRepository,
  command: RegisterTrialCommand,
): Promise<AuthSession> {
  const session = await authRepository.registerTrial(command)
  sessionRepository.save(session)
  return session
}

/** Clear the active authentication session. */
export function signOut(sessionRepository: SessionRepository): void {
  sessionRepository.clear()
}
