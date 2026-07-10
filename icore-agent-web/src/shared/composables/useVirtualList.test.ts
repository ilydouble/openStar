// @ts-nocheck
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { ref } from 'vue'

import { useVirtualList } from './useVirtualList'

test('useVirtualList exposes only rows near the current scroll window', () => {
  const items = ref(Array.from({ length: 20 }, (_, index) => ({ id: `m-${index}` })))
  const list = useVirtualList({
    items,
    getKey: (item) => item.id,
    estimateHeight: () => 100,
    itemGap: 24,
    overscan: 1,
  })

  list.syncContainer({ scrollTop: 500, clientHeight: 300 })

  assert.equal(list.visibleItems.value.length > 0, true)
  assert.equal(list.visibleItems.value.length < items.value.length, true)
  assert.equal(list.totalHeight.value, 20 * 100 + 19 * 24)
  assert.equal(list.offsetY.value >= 0, true)

  list.destroy()
})

test('useVirtualList resets cached measurements when the list shrinks', () => {
  const items = ref([{ id: 'a' }, { id: 'b' }, { id: 'c' }])
  const list = useVirtualList({
    items,
    getKey: (item) => item.id,
    estimateHeight: () => 80,
  })

  list.resetMeasurements()
  items.value = [{ id: 'a' }]
  list.syncContainer({ scrollTop: 0, clientHeight: 240 })

  assert.equal(list.visibleItems.value.length, 1)
  list.destroy()
})
