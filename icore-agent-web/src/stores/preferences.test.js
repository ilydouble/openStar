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

test('locale preference defaults to Chinese for the international product', () => {
  assert.equal(getLocalePreference(memoryStorage()), 'zh-CN')
})

test('locale preference keeps an explicit English selection', () => {
  const storage = memoryStorage({ [LOCALE_STORAGE_KEY]: 'en-US' })

  assert.equal(getLocalePreference(storage), 'en-US')
})
