import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import enUS from '../locales/en-US.js'
import zhCN from '../locales/zh-CN.js'

test('account console copy is framed around Commerce OS diagnosis plans', () => {
  assert.equal(zhCN.account.title, '账户与诊断服务')
  assert.equal(zhCN.account.openWorkspace, '打开 Commerce OS')
  assert.equal(zhCN.account.upgrade, '升级服务')
  assert.equal(enUS.account.title, 'Account and diagnosis services')
  assert.equal(enUS.account.openWorkspace, 'Open Commerce OS')
  assert.equal(enUS.account.upgrade, 'Upgrade service')
})

test('upgrade modal uses purchasable commerce service tiers', () => {
  assert.equal(zhCN.quotaModal.plans.pro.name, '免费诊断')
  assert.equal(zhCN.quotaModal.plans.team.name, '试点服务')
  assert.equal(zhCN.quotaModal.plans.premium.name, '持续运营')
  assert.equal(zhCN.quotaModal.plans.byok.name, '联系顾问')
  assert.equal(zhCN.quotaModal.plans.team.cta, '升级试点服务')
  assert.equal(zhCN.quotaModal.plans.premium.cta, '升级持续运营')

  assert.equal(enUS.quotaModal.plans.pro.name, 'Free Diagnosis')
  assert.equal(enUS.quotaModal.plans.team.name, 'Pilot Service')
  assert.equal(enUS.quotaModal.plans.premium.name, 'Continuous Ops')
  assert.equal(enUS.quotaModal.plans.byok.name, 'Talk to an advisor')
  assert.equal(enUS.quotaModal.plans.team.cta, 'Upgrade to Pilot Service')
  assert.equal(enUS.quotaModal.plans.premium.cta, 'Upgrade to Continuous Ops')
})

test('account page opens the commerce workspace first', () => {
  const content = readFileSync(new URL('../views/AccountView.vue', import.meta.url), 'utf8')

  assert.match(content, /<RouterLink to="\/commerce"/)
})

test('account page and quota modal expose simulated payment upgrades', () => {
  const account = readFileSync(new URL('../views/AccountView.vue', import.meta.url), 'utf8')
  const quota = readFileSync(new URL('../components/QuotaExceededModal.vue', import.meta.url), 'utf8')

  assert.match(account, /SimulatedPaymentModal/)
  assert.match(account, /openSimulatedPayment\('pilot'\)/)
  assert.match(quota, /SimulatedPaymentModal/)
  assert.match(quota, /openSimulatedPayment\(plan\.paymentPlan\)/)
})
