import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import enUS from '../locales/en-US.js'
import zhCN from '../locales/zh-CN.js'

test('english landing copy focuses V1 on CSV operations diagnosis', () => {
  assert.equal(
    enUS.landing.hero.title,
    'Upload commerce spreadsheets. Get an AI operations diagnosis.',
  )
  assert.equal(enUS.landing.hero.primaryCta, 'Generate sample diagnosis')
  assert.equal(enUS.landing.hero.secondaryCta, 'Upload CSV for free diagnosis')
})

test('chinese landing copy focuses V1 on CSV operations diagnosis', () => {
  assert.equal(
    zhCN.landing.hero.title,
    '上传电商运营表格，生成 AI 运营诊断',
  )
  assert.equal(zhCN.landing.hero.primaryCta, '生成示例诊断')
  assert.equal(zhCN.landing.hero.secondaryCta, '上传 CSV 免费诊断')
})

test('chinese plans sell diagnosis outcomes instead of generic seats', () => {
  const [free, pilot, ops] = zhCN.landing.plans.tiers

  assert.equal(free.name, '免费诊断')
  assert.equal(pilot.name, '试点服务')
  assert.equal(ops.name, '持续运营')
  assert.equal(pilot.price, '¥499-1999')
  assert.equal(pilot.period, '/次或/月')
  assert.ok(pilot.features.includes('真实经营数据诊断'))
})

test('english plans sell diagnosis outcomes instead of generic seats', () => {
  const [free, pilot, ops] = enUS.landing.plans.tiers

  assert.equal(free.name, 'Free Diagnosis')
  assert.equal(pilot.name, 'Pilot Service')
  assert.equal(ops.name, 'Continuous Ops')
  assert.equal(pilot.price, '¥499-1999')
  assert.equal(pilot.period, '/report or /mo')
  assert.ok(pilot.features.includes('Diagnosis with real operating data'))
})

test('authenticated landing plans can open the simulated payment flow', () => {
  const content = readFileSync(new URL('../components/landing/PlansSection.vue', import.meta.url), 'utf8')

  assert.match(content, /SimulatedPaymentModal/)
  assert.match(content, /openSimulatedPayment\(tier/)
})
