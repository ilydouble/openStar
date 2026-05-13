import test from 'node:test'
import assert from 'node:assert/strict'

import { routes } from '../src/router.js'
import zhCN from '../src/locales/zh-CN.js'
import enUS from '../src/locales/en-US.js'
import { existsSync, readFileSync } from 'node:fs'

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

test('landing copy matches the updated homepage messaging from 网站修改.docx', () => {
  assert.equal(zhCN.landing.hero.title, '告别零散工具与重复劳动 一套AI工作流标准化出海全流程')
  assert.equal(zhCN.landing.hero.panel.focusTitle, '统一运营驾驶舱整合内容、知识与增长全链路')
  assert.equal(zhCN.landing.solutions.title, '覆盖出海全周期 五大标准化核心工作流')
  assert.equal(zhCN.landing.results.items[1].body, '告别外包翻译依赖，实现多语言内容批量自动化生产，同时保障品牌语气统一与内容迭代效率。')
  assert.equal(zhCN.landing.workflow.subtitle, '从素材接入到成果交付，iCore 是企业专属的 AI 数字运营底盘，而非普通对话式 AI 工具。')
  assert.equal(zhCN.landing.plans.title, '全梯度服务体系，从试用体验到企业级定制交付')
  assert.equal(zhCN.landing.finalCta.title, 'iCore：专注为出海团队创造可量化业务结果')

  assert.equal(enUS.landing.hero.title, 'Replace scattered tools and repeated labor with one standardized AI workflow for cross-border growth')
  assert.equal(enUS.landing.hero.panel.focusTitle, 'One operating cockpit unifies content, knowledge, and growth execution')
  assert.equal(enUS.landing.solutions.title, 'Five standardized core workflows across the full cross-border growth cycle')
  assert.equal(enUS.landing.results.items[1].label, '60% lower multilingual content cost')
  assert.equal(enUS.landing.workflow.subtitle, 'From material intake to deliverables, iCore acts as a dedicated AI operating foundation instead of a generic chat tool.')
  assert.equal(enUS.landing.plans.title, 'A full service ladder from trial access to enterprise-grade custom delivery')
  assert.equal(enUS.landing.finalCta.title, 'iCore: built to create measurable business results for cross-border teams')
})

test('landing visual components reference the generated image assets', () => {
  const heroSource = readFileSync(new URL('../src/components/landing/HeroSection.vue', import.meta.url), 'utf8')
  const solutionsSource = readFileSync(new URL('../src/components/landing/SolutionsSection.vue', import.meta.url), 'utf8')
  const finalCtaSource = readFileSync(new URL('../src/components/landing/FinalCtaSection.vue', import.meta.url), 'utf8')

  assert.ok(heroSource.includes('hero-ops-cockpit.jpg'), 'expected hero section image asset reference')
  assert.ok(solutionsSource.includes('solutions-workflows.jpg'), 'expected solutions section image asset reference')
  assert.ok(finalCtaSource.includes('final-cta-platform.jpg'), 'expected final CTA image asset reference')

  assert.ok(existsSync(new URL('../src/assets/landing/hero-ops-cockpit.jpg', import.meta.url)), 'expected hero image asset file')
  assert.ok(existsSync(new URL('../src/assets/landing/solutions-workflows.jpg', import.meta.url)), 'expected solutions image asset file')
  assert.ok(existsSync(new URL('../src/assets/landing/final-cta-platform.jpg', import.meta.url)), 'expected final CTA image asset file')
})
