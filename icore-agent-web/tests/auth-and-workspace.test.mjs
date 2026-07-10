import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { readAgentError } from '../src/api/agent.js'
import { routes } from '../src/router'
import zhCN from '../src/shared/i18n/locales/zh-CN'
import enUS from '../src/shared/i18n/locales/en-US'

test('router exposes auth and account routes and protects workspace', () => {
  const authRoute = routes.find((route) => route.path === '/auth')
  const accountRoute = routes.find((route) => route.path === '/account')
  const enterpriseRoute = routes.find((route) => route.path === '/enterprise')
  const workspaceRoute = routes.find((route) => route.path === '/app')

  assert.ok(authRoute, 'expected an auth route')
  assert.ok(accountRoute, 'expected an account route')
  assert.ok(enterpriseRoute, 'expected an enterprise/contact route')
  assert.equal(workspaceRoute?.meta?.requiresAuth, true, 'workspace should require auth')
  assert.equal(accountRoute?.meta?.requiresAuth, true, 'account page should require auth')
})

test('workspace locales expose scenario content and account copy', () => {
  for (const locale of [zhCN, enUS]) {
    assert.ok(locale.account, 'expected account namespace')
    assert.ok(Array.isArray(locale.home.shortcuts), 'expected workspace shortcuts')
    assert.ok(locale.home.shortcuts.length >= 5, 'expected business scenario shortcuts')
    assert.ok(Array.isArray(locale.home.templates), 'expected scenario template definitions')
    assert.ok(locale.home.templates.length >= 5, 'expected at least five scenario templates')
    assert.ok(
      locale.home.templates.every((item) => Array.isArray(item.sections) && item.sections.length >= 3),
      'expected structured output sections for every scenario',
    )
    assert.ok(locale.account.plan, 'expected account plan copy')
  }
})

test('home sidebar links only use registered workspace route names', () => {
  const sidebarSource = readFileSync(new URL('../src/components/HomeSidebar.vue', import.meta.url), 'utf8')

  assert.ok(sidebarSource.includes(":to=\"{ name: 'workspace' }\""), 'expected workspace route link in sidebar')
  assert.ok(!sidebarSource.includes(":to=\"{ name: 'chat' }\""), 'expected sidebar to avoid removed chat route name')
})

test('agent api surfaces quota detail instead of a generic request failure', async () => {
  const quotaResponse = new Response(JSON.stringify({ detail: 'messages quota exceeded for trial' }), {
    status: 402,
    headers: { 'Content-Type': 'application/json' },
  })
  const genericResponse = new Response('Internal Server Error', {
    status: 500,
    headers: { 'Content-Type': 'text/plain' },
  })

  await assert.rejects(
    () => readAgentError(quotaResponse),
    /messages quota exceeded for trial/,
    'expected quota detail to be preserved in thrown error',
  )
  await assert.rejects(
    () => readAgentError(genericResponse),
    /服务器出现问题，请稍后再试。/,
    'expected localized fallback when no structured detail is available',
  )
})
