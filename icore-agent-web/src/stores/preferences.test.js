import test from 'node:test'
import assert from 'node:assert/strict'

import { getLocalePreference, LOCALE_STORAGE_KEY } from './preferences.js'

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial))
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null
    },
    setItem(key, value) {
      values.set(key, value)
    },
  }
}

test('locale preference defaults to English for international users', () => {
  assert.equal(getLocalePreference(memoryStorage()), 'en-US')
})

test('locale preference keeps an explicit Chinese selection', () => {
  const storage = memoryStorage({ [LOCALE_STORAGE_KEY]: 'zh-CN' })

  assert.equal(getLocalePreference(storage), 'zh-CN')
})
