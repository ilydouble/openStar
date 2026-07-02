import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applySimulatedEntitlement,
  createSimulatedCheckout,
  getSimulatedCheckoutPlan,
  persistSimulatedEntitlement,
} from './simulatedCheckout.js'

test('simulated checkout creates a deterministic dev order for paid service upgrades', () => {
  const checkout = createSimulatedCheckout('pilot', {
    now: new Date('2026-07-02T12:34:56.000Z'),
    seed: 'demo-user',
  })

  assert.equal(checkout.planKey, 'pilot')
  assert.equal(checkout.planCode, 'team')
  assert.equal(checkout.amountCents, 49900)
  assert.equal(checkout.currency, 'CNY')
  assert.equal(checkout.status, 'pending')
  assert.match(checkout.orderNo, /^SIM-PILOT-20260702123456-/)
  assert.match(checkout.payUrl, /^simulated:\/\/wechatpay\/native\//)
})

test('simulated checkout exposes continuous operations as a premium monthly plan', () => {
  const plan = getSimulatedCheckoutPlan('ops')

  assert.equal(plan.planCode, 'premium')
  assert.equal(plan.amountCents, 99900)
  assert.equal(plan.billingPeriod, 'monthly')
})

test('simulated paid checkout overlays the account plan entitlement', () => {
  const storage = createMemoryStorage()
  const checkout = {
    ...createSimulatedCheckout('ops', {
      now: new Date('2026-07-02T12:34:56.000Z'),
      seed: 'demo-user',
    }),
    status: 'paid',
  }

  persistSimulatedEntitlement(checkout, { storage })
  const plan = applySimulatedEntitlement(
    {
      plan: 'trial',
      label: 'Trial',
      limits: { tasks: 10, attachments: 10 },
      usage: { tasks: 10, attachments: 1 },
    },
    { storage },
  )

  assert.equal(plan.plan, 'premium')
  assert.equal(plan.label, '持续运营')
  assert.equal(plan.limits.tasks, 5000)
  assert.equal(plan.limits.attachments, 2000)
  assert.equal(plan.simulated_entitlement.enabled, true)
  assert.equal(plan.simulated_entitlement.order_no, checkout.orderNo)
})

function createMemoryStorage() {
  const values = new Map()
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  }
}
