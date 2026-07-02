const SIMULATED_PLANS = {
  pilot: {
    planKey: 'pilot',
    planCode: 'team',
    billingPeriod: 'once',
    currency: 'CNY',
    amountCents: 49900,
  },
  ops: {
    planKey: 'ops',
    planCode: 'premium',
    billingPeriod: 'monthly',
    currency: 'CNY',
    amountCents: 99900,
  },
}

/** Return the simulated checkout plan mapped to the current Commerce OS service tier. */
export function getSimulatedCheckoutPlan(planKey) {
  return SIMULATED_PLANS[planKey] || SIMULATED_PLANS.pilot
}

/** Format the simulated checkout amount for display in the payment modal. */
export function formatSimulatedAmount(amountCents, currency = 'CNY') {
  const symbol = currency === 'CNY' ? '¥' : `${currency} `
  return `${symbol}${(Number(amountCents) / 100).toFixed(2)}`
}

/** Create a deterministic development-only payment order without calling a provider. */
export function createSimulatedCheckout(planKey, options = {}) {
  const plan = getSimulatedCheckoutPlan(planKey)
  const now = options.now instanceof Date ? options.now : new Date()
  const seed = String(options.seed || Math.random().toString(36).slice(2))
  const timestamp = now.toISOString().replace(/\D/g, '').slice(0, 14)
  const suffix = hashSeed(`${plan.planKey}:${seed}:${timestamp}`).slice(0, 8).toUpperCase()
  const orderNo = `SIM-${plan.planKey.toUpperCase()}-${timestamp}-${suffix}`

  return {
    ...plan,
    orderNo,
    status: 'pending',
    createdAt: now.toISOString(),
    payUrl: `simulated://wechatpay/native/${orderNo}`,
  }
}

/** Mark a simulated order as paid to mirror the real payment callback result. */
export function completeSimulatedCheckout(checkout, options = {}) {
  const paidAt = options.now instanceof Date ? options.now.toISOString() : new Date().toISOString()
  return {
    ...checkout,
    status: 'paid',
    paidAt,
  }
}

/** Build a short stable hash for simulated order numbers. */
function hashSeed(value) {
  let hash = 2166136261
  for (const char of value) {
    hash ^= char.charCodeAt(0)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36).padStart(8, '0')
}
