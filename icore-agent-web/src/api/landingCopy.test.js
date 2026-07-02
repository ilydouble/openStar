import test from 'node:test'
import assert from 'node:assert/strict'

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
