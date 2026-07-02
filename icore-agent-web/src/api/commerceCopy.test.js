import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import enUS from '../locales/en-US.js'
import zhCN from '../locales/zh-CN.js'

test('commerce workspace has Chinese and English dashboard copy', () => {
  assert.equal(zhCN.commerce.dashboard.title, 'AI 运营诊断')
  assert.equal(zhCN.commerce.shell.uploadButton, '上传 CSV')
  assert.equal(zhCN.commerce.sidebar.nav.diagnosis, '诊断')

  assert.equal(enUS.commerce.dashboard.title, 'AI Operations Diagnosis')
  assert.equal(enUS.commerce.shell.uploadButton, 'Upload CSVs')
  assert.equal(enUS.commerce.sidebar.nav.diagnosis, 'Diagnosis')
})

test('commerce workspace components use locale copy instead of hard-coded English', () => {
  const files = [
    '../components/commerce/CommerceSidebar.vue',
    '../components/commerce/CommerceShell.vue',
    '../views/CommerceDashboardView.vue',
  ]

  for (const file of files) {
    const content = readFileSync(new URL(file, import.meta.url), 'utf8')
    assert.doesNotMatch(content, /AI Operations Diagnosis|Load sample CSVs|CSV diagnosis pilot/)
  }
})
