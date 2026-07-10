/** Application error carrying the upgrade context for exhausted account quota. */
export class QuotaExceededError extends Error {
  constructor(
    readonly currentPlan = 'trial',
    readonly upgradeUrl = '/pricing',
  ) {
    super('quota_exceeded')
    this.name = 'QuotaExceededError'
  }
}
