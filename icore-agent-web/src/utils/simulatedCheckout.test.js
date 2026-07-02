import test from 'node:test'
import assert from 'node:assert/strict'

import { createSimulatedCheckout, getSimulatedCheckoutPlan } from './simulatedCheckout.js'

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
