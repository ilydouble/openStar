import test from 'node:test'
import assert from 'node:assert/strict'

import { routes } from '../src/router.js'
import zhCN from '../src/locales/zh-CN.js'
import enUS from '../src/locales/en-US.js'

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
