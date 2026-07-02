import test from 'node:test'
import assert from 'node:assert/strict'

import enUS from '../locales/en-US.js'
import zhCN from '../locales/zh-CN.js'

test('english landing copy positions iCore as Commerce OS', () => {
  assert.equal(
    enUS.landing.hero.title,
    'AI operations dashboard for small cross-border commerce teams.',
  )
  assert.equal(enUS.landing.hero.primaryCta, 'View sample operations brief')
  assert.equal(enUS.landing.hero.secondaryCta, 'Upload CSV for a free diagnosis')
})

test('chinese landing copy positions iCore as Commerce OS', () => {
  assert.equal(
    zhCN.landing.hero.title,
    '小型跨境团队的 AI 运营驾驶舱',
  )
  assert.equal(zhCN.landing.hero.primaryCta, '查看示例运营日报')
  assert.equal(zhCN.landing.hero.secondaryCta, '上传 CSV 免费诊断')
})
