import { computed, getCurrentInstance, onBeforeUnmount, ref, unref, watch } from 'vue'
import type { Ref } from 'vue'

const DEFAULT_ITEM_HEIGHT = 96

export type VirtualListKey = string | number

export interface UseVirtualListOptions<T> {
  items: Ref<T[]> | T[]
  getKey?: (item: T, index: number) => VirtualListKey
  estimateHeight?: (item: T, index: number) => number
  itemGap?: number
  overscan?: number
}

/**
 * Windowed list helper for variable-height rows with measured caching.
 */
export function useVirtualList<T>(options: UseVirtualListOptions<T>) {
  const scrollTop = ref(0)
  const containerHeight = ref(320)
  const overscan = options.overscan ?? 3
  const itemGap = options.itemGap ?? 24
  const measuredHeights = ref(new Map<VirtualListKey, number>())
  const rowElements = new Map<string, HTMLElement>()

  /** Resolve the reactive list backing the virtual window. */
  function resolveItems(): T[] {
    const items = unref(options.items)
    return Array.isArray(items) ? items : []
  }

  /** Resolve a stable cache key for one row. */
  function getItemKey(item: T, index: number): VirtualListKey {
    if (typeof options.getKey === 'function') {
      return options.getKey(item, index)
    }
    return index
  }

  /** Estimate row height before the row has been measured in the DOM. */
  function estimateItemHeight(item: T, index: number): number {
    if (typeof options.estimateHeight === 'function') {
      return Math.max(0, Number(options.estimateHeight(item, index)) || 0)
    }
    return DEFAULT_ITEM_HEIGHT
  }

  /** Return cached or estimated height for one row. */
  function getRowHeight(item: T, index: number): number {
    const key = getItemKey(item, index)
    const measured = measuredHeights.value.get(key)
    if (measured != null && measured > 0) {
      return measured
    }
    return estimateItemHeight(item, index)
  }

  const layout = computed(() => {
    const items = resolveItems()
    const offsets: number[] = []
    const heights: number[] = []
    let total = 0

    for (let index = 0; index < items.length; index += 1) {
      offsets.push(total)
      const height = getRowHeight(items[index], index)
      heights.push(height)
      total += height
      if (index < items.length - 1) {
        total += itemGap
      }
    }

    return { offsets, heights, total }
  })

  const totalHeight = computed(() => layout.value.total)

  /** Find the first row intersecting a scroll offset. */
  function findStartIndex(position: number): number {
    const { offsets, heights } = layout.value
    if (!offsets.length) return 0

    let low = 0
    let high = offsets.length - 1
    while (low < high) {
      const mid = Math.ceil((low + high) / 2)
      if (offsets[mid] <= position) {
        low = mid
      } else {
        high = mid - 1
      }
    }

    const startOffset = offsets[low]
    const startHeight = heights[low]
    if (position > startOffset + startHeight && low < offsets.length - 1) {
      return low + 1
    }
    return low
  }

  const startIndex = computed(() =>
    Math.max(0, findStartIndex(scrollTop.value) - overscan),
  )

  const endIndex = computed(() => {
    const items = resolveItems()
    const viewportBottom = scrollTop.value + containerHeight.value
    const { offsets } = layout.value
    let index = startIndex.value

    while (index < items.length && offsets[index] <= viewportBottom) {
      index += 1
    }

    return Math.min(items.length, index + overscan + 1)
  })

  const visibleItems = computed(() => {
    const items = resolveItems()
    return items.slice(startIndex.value, endIndex.value).map((item, sliceIndex) => ({
      item,
      index: startIndex.value + sliceIndex,
    }))
  })

  const offsetY = computed(() => layout.value.offsets[startIndex.value] || 0)

  let resizeObserver: ResizeObserver | null = null

  /** Lazily create the shared ResizeObserver for measured rows. */
  function ensureObserver() {
    if (resizeObserver || typeof ResizeObserver === 'undefined') return
    resizeObserver = new ResizeObserver((entries) => {
      let changed = false
      const next = new Map(measuredHeights.value)

      for (const entry of entries) {
        const key = (entry.target as HTMLElement).dataset.virtualKey
        if (!key) continue
        const height = Math.ceil(entry.borderBoxSize?.[0]?.blockSize ?? entry.contentRect.height)
        if (height > 0 && next.get(key) !== height) {
          next.set(key, height)
          changed = true
        }
      }

      if (changed) {
        measuredHeights.value = next
      }
    })
  }

  /** Register or unregister one rendered row for height measurement. */
  function setRowRef(el: HTMLElement | null, item: T, index: number): void {
    ensureObserver()
    const key = String(getItemKey(item, index))

    if (!el) {
      const prev = rowElements.get(key)
      if (prev && resizeObserver) {
        resizeObserver.unobserve(prev)
      }
      rowElements.delete(key)
      return
    }

    el.dataset.virtualKey = key
    rowElements.set(key, el)
    resizeObserver?.observe(el)
  }

  /** Sync scroll position and viewport size from the list container. */
  function syncContainer(el: { scrollTop: number; clientHeight: number } | null): void {
    if (!el) return
    scrollTop.value = el.scrollTop
    containerHeight.value = el.clientHeight
  }

  /** Clear cached measurements after the list shrinks or is replaced. */
  function resetMeasurements() {
    measuredHeights.value = new Map()
  }

  /** Disconnect observers created by this list instance. */
  function destroy() {
    resizeObserver?.disconnect()
    resizeObserver = null
    rowElements.clear()
  }

  watch(
    () => resolveItems().length,
    (next, prev) => {
      if (next < prev) {
        resetMeasurements()
      }
    },
  )

  if (getCurrentInstance()) {
    onBeforeUnmount(() => {
      destroy()
    })
  }

  return {
    visibleItems,
    totalHeight,
    offsetY,
    syncContainer,
    setRowRef,
    resetMeasurements,
    destroy,
  }
}
