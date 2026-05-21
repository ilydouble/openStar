import { computed, ref, unref } from 'vue'

/**
 * Windowed list helper that keeps only visible rows in the DOM.
 * @param {{
 *   items: import('vue').Ref<Array>,
 *   itemHeight: number | import('vue').Ref<number> | (() => number),
 *   overscan?: number,
 * }} options
 */
export function useVirtualList(options) {
  const scrollTop = ref(0)
  const containerHeight = ref(240)
  const overscan = options.overscan ?? 4

  /** Resolve the current fixed row height from a number, ref, or getter. */
  function resolveItemHeight() {
    if (typeof options.itemHeight === 'function') {
      return options.itemHeight()
    }
    return Number(unref(options.itemHeight) || 0)
  }

  const itemCount = computed(() => options.items.value.length)
  const totalHeight = computed(() => itemCount.value * resolveItemHeight())

  const startIndex = computed(() =>
    Math.max(0, Math.floor(scrollTop.value / resolveItemHeight()) - overscan),
  )

  const endIndex = computed(() => {
    const itemHeight = resolveItemHeight()
    const visibleCount = Math.ceil(containerHeight.value / itemHeight) + overscan * 2
    return Math.min(itemCount.value, startIndex.value + visibleCount)
  })

  const visibleItems = computed(() =>
    options.items.value.slice(startIndex.value, endIndex.value).map((item, index) => ({
      item,
      index: startIndex.value + index,
    })),
  )

  const offsetY = computed(() => startIndex.value * resolveItemHeight())

  /** Sync scroll position and viewport size from the list container. */
  function syncContainer(el) {
    if (!el) return
    scrollTop.value = el.scrollTop
    containerHeight.value = el.clientHeight
  }

  return {
    visibleItems,
    totalHeight,
    offsetY,
    syncContainer,
  }
}
