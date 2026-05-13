import test from 'node:test'
import assert from 'node:assert/strict'

import { routes } from '../src/router.js'
import zhCN from '../src/locales/zh-CN.js'
import enUS from '../src/locales/en-US.js'
import { readFileSync } from 'node:fs'

test('router exposes marketing home, app workspace, and chat compatibility redirect', () => {
  const homeRoute = routes.find((route) => route.path === '/')
  const appRoute = routes.find((route) => route.path === '/app')
  const chatRoute = routes.find((route) => route.path === '/chat/:sessionId?')

  assert.ok(homeRoute, 'expected a marketing route at /')
  assert.ok(appRoute, 'expected a workspace route at /app')
  assert.equal(typeof chatRoute?.redirect, 'function', 'expected chat route compatibility redirect')
})

test('landing content namespace exists in both locales', () => {
  for (const locale of [zhCN, enUS]) {
    assert.ok(locale.landing, 'expected landing namespace')
    assert.ok(locale.landing.nav, 'expected landing nav content')
    assert.ok(locale.landing.hero, 'expected landing hero content')
    assert.ok(locale.landing.solutions?.items?.length >= 5, 'expected at least five solution cards')
    assert.ok(locale.landing.plans?.tiers?.length === 3, 'expected three pricing tiers')
  }
})

test('landing keeps api.stellarmesh.net in footer extra services instead of a standalone section', () => {
  const landingViewSource = readFileSync(new URL('../src/views/LandingView.vue', import.meta.url), 'utf8')

  assert.ok(landingViewSource.includes('<LandingFooter />'), 'expected landing footer to stay mounted')
  assert.ok(!landingViewSource.includes('<RelatedBusinessSection />'), 'expected related business section to be removed from main landing flow')

  for (const locale of [zhCN, enUS]) {
    assert.ok(locale.landing.footer?.extraServicesLabel, 'expected footer extra services label')
    assert.ok(locale.landing.footer?.extraServices?.length >= 1, 'expected at least one extra service entry')
  }
})
