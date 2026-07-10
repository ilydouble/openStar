import { createAuthApplication } from './application/createAuthApplication'
import { HttpAuthRepository } from './infrastructure/http/authApi'
import { BrowserSessionRepository } from './infrastructure/storage/browserSessionRepository'

export const authSessionRepository = new BrowserSessionRepository()

export const authApplication = createAuthApplication({
  authRepository: new HttpAuthRepository(),
  sessionRepository: authSessionRepository,
})
