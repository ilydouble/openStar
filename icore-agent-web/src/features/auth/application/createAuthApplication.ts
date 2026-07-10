import type {
  EmailLoginCommand,
  RegisterTrialCommand,
  VerificationCodeCommand,
} from '../domain/models/authSession'
import type { AuthRepository } from '../domain/repositories/authRepository'
import type { SessionRepository } from '../domain/repositories/sessionRepository'
import {
  loginWithEmail,
  registerTrial,
  sendVerificationCode,
  signOut,
} from './use-cases/authenticate'

export interface AuthApplicationDependencies {
  authRepository: AuthRepository
  sessionRepository: SessionRepository
}

/** Bind auth use cases to their repositories for presentation and cross-feature consumers. */
export function createAuthApplication(dependencies: AuthApplicationDependencies) {
  const { authRepository, sessionRepository } = dependencies

  return {
    sendVerificationCode: (command: VerificationCodeCommand) =>
      sendVerificationCode(authRepository, command),
    emailLogin: (command: EmailLoginCommand) =>
      loginWithEmail(authRepository, sessionRepository, command),
    registerTrial: (command: RegisterTrialCommand) =>
      registerTrial(authRepository, sessionRepository, command),
    signOut: () => signOut(sessionRepository),
    getAccessToken: () => sessionRepository.getAccessToken(),
    getCurrentUser: () => sessionRepository.getUser(),
    isAuthenticated: () => Boolean(sessionRepository.getAccessToken()),
  }
}
