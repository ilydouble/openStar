import test from 'node:test'
import assert from 'node:assert/strict'

import { authenticatedHomeRouteName, routes } from './router.js'

test('commerce route is an authenticated operations workspace', () => {
  const route = routes.find((item) => item.name === 'commerce')

  assert.ok(route, 'commerce route should be registered')
  assert.equal(route.path, '/commerce')
  assert.equal(route.meta?.requiresAuth, true)
})

test('authenticated users land in the commerce workspace by default', () => {
  assert.equal(authenticatedHomeRouteName, 'commerce')
})
