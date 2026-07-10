export { authApplication } from './composition'
export type {
  AuthSession,
  AuthUser,
  EmailLoginCommand,
  RegisterTrialCommand,
  VerificationCodeCommand,
  VerificationPurpose,
} from './domain/models/authSession'

/** Load the routed authentication page without pulling it into the application entry chunk. */
export function loadAuthPage() {
  return import('./presentation/pages/AuthPage.vue')
}
