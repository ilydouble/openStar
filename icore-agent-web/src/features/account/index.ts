export { accountApplication } from './composition'
export type {
  AccountPlan,
  AccountProject,
  ProjectList,
  SyncProjectCommand,
} from './domain/models/account'

/** Load the account page through the feature's public route boundary. */
export function loadAccountPage() {
  return import('./presentation/pages/AccountPage.vue')
}
