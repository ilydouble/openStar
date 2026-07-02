import test from 'node:test'
import assert from 'node:assert/strict'

import { authenticatedHomeRouteName, resolvePostAuthRoute, routes } from './router.js'

test('commerce route is an authenticated operations workspace', () => {
  const route = routes.find((item) => item.name === 'commerce')

  assert.ok(route, 'commerce route should be registered')
  assert.equal(route.path, '/commerce')
  assert.equal(route.meta?.requiresAuth, true)
})

test('authenticated users land in the commerce workspace by default', () => {
  assert.equal(authenticatedHomeRouteName, 'commerce')
})

test('post-auth routing returns the explicit internal redirect first', () => {
  assert.equal(resolvePostAuthRoute({ redirect: '/app/session-1' }), '/app/session-1')
})

test('post-auth routing falls back to commerce when redirect is missing or unsafe', () => {
  assert.deepEqual(resolvePostAuthRoute({}), { name: 'commerce' })
  assert.deepEqual(resolvePostAuthRoute({ redirect: 'https://evil.example/app' }), { name: 'commerce' })
  assert.deepEqual(resolvePostAuthRoute({ redirect: '//evil.example/app' }), { name: 'commerce' })
})
