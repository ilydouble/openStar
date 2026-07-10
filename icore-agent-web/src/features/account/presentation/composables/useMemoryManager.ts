import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { accountApplication } from '../../composition'
import type { MemoryCategory, MemoryFact } from '../../domain/models/account'

const CATEGORY_ORDER: MemoryCategory[] = [
  'personal',
  'work_context',
  'goal',
  'preference',
  'constraint',
]
const CATEGORY_PREVIEW_LIMIT = 3

/** Manage durable-memory loading, grouping, editing, and deletion. */
export function useMemoryManager() {
  const { t, locale } = useI18n()
  const loading = ref(true)
  const saving = ref(false)
  const deletingId = ref<number | null>(null)
  const error = ref('')
  const facts = ref<MemoryFact[]>([])
  const editingId = ref<number | null>(null)
  const draftValue = ref('')
  const expandedCategories = ref<Partial<Record<MemoryCategory, boolean>>>({})

  const groupedFacts = computed<Record<MemoryCategory, MemoryFact[]>>(() => {
    const groups = Object.fromEntries(
      CATEGORY_ORDER.map((category) => [category, [] as MemoryFact[]]),
    ) as Record<MemoryCategory, MemoryFact[]>
    for (const fact of facts.value) groups[fact.category].push(fact)
    return groups
  })
  const visibleCategories = computed(() =>
    CATEGORY_ORDER.filter((category) => groupedFacts.value[category].length > 0),
  )

  /** Return all facts for one category. */
  function factsForCategory(category: MemoryCategory): MemoryFact[] {
    return groupedFacts.value[category]
  }

  /** Return whether one category is expanded. */
  function isCategoryExpanded(category: MemoryCategory): boolean {
    return Boolean(expandedCategories.value[category])
  }

  /** Toggle expanded state for one category. */
  function toggleCategoryExpanded(category: MemoryCategory): void {
    expandedCategories.value = {
      ...expandedCategories.value,
      [category]: !expandedCategories.value[category],
    }
  }

  /** Return whether one category exceeds the preview limit. */
  function categoryHasMore(category: MemoryCategory): boolean {
    return factsForCategory(category).length > CATEGORY_PREVIEW_LIMIT
  }

  /** Count facts hidden by the collapsed preview. */
  function hiddenFactCount(category: MemoryCategory): number {
    return Math.max(factsForCategory(category).length - CATEGORY_PREVIEW_LIMIT, 0)
  }

  /** Return facts currently visible for one category. */
  function visibleFactsForCategory(category: MemoryCategory): MemoryFact[] {
    const items = factsForCategory(category)
    return isCategoryExpanded(category) ? items : items.slice(0, CATEGORY_PREVIEW_LIMIT)
  }

  /** Load active durable-memory facts. */
  async function loadMemory(): Promise<void> {
    loading.value = true
    error.value = ''
    expandedCategories.value = {}
    try {
      facts.value = (await accountApplication.loadMemory()).facts
    } catch (cause: unknown) {
      error.value = readErrorMessage(cause, t('account.memory.loadFailed'))
      facts.value = []
    } finally {
      loading.value = false
    }
  }

  /** Return the translated category label. */
  function categoryLabel(category: MemoryCategory): string {
    return t(`account.memory.categories.${category}`)
  }

  /** Format a memory key for display. */
  function formatKey(key: string): string {
    return key.replace(/_/g, ' ')
  }

  /** Format confidence as a whole-number percentage. */
  function formatConfidence(value: number): string {
    return `${Math.round(value * 100)}%`
  }

  /** Format a unix timestamp for the active locale. */
  function formatDate(timestamp: number): string {
    if (!timestamp) return '-'
    return new Intl.DateTimeFormat(locale.value, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(timestamp * 1000))
  }

  /** Begin inline editing for one fact. */
  function startEdit(fact: MemoryFact): void {
    editingId.value = fact.id
    draftValue.value = fact.value
  }

  /** Cancel inline editing. */
  function cancelEdit(): void {
    editingId.value = null
    draftValue.value = ''
  }

  /** Persist one edited memory fact. */
  async function saveEdit(factId: number): Promise<void> {
    const value = draftValue.value.trim()
    if (!value) return
    saving.value = true
    error.value = ''
    try {
      const updated = await accountApplication.updateMemoryFact(factId, value)
      facts.value = facts.value.map((fact) => fact.id === factId ? updated : fact)
      cancelEdit()
    } catch (cause: unknown) {
      error.value = readErrorMessage(cause, t('account.memory.saveFailed'))
    } finally {
      saving.value = false
    }
  }

  /** Delete one fact after browser confirmation. */
  async function confirmDelete(factId: number): Promise<void> {
    if (!window.confirm(t('account.memory.deleteConfirm'))) return
    deletingId.value = factId
    error.value = ''
    try {
      await accountApplication.deleteMemoryFact(factId)
      facts.value = facts.value.filter((fact) => fact.id !== factId)
      if (editingId.value === factId) cancelEdit()
    } catch (cause: unknown) {
      error.value = readErrorMessage(cause, t('account.memory.deleteFailed'))
    } finally {
      deletingId.value = null
    }
  }

  onMounted(loadMemory)

  return {
    cancelEdit,
    categoryHasMore,
    categoryLabel,
    confirmDelete,
    deletingId,
    draftValue,
    editingId,
    error,
    facts,
    formatConfidence,
    formatDate,
    formatKey,
    groupedFacts,
    hiddenFactCount,
    isCategoryExpanded,
    loadMemory,
    loading,
    saveEdit,
    saving,
    startEdit,
    t,
    toggleCategoryExpanded,
    visibleCategories,
    visibleFactsForCategory,
  }
}

/** Convert an unknown account failure into safe user-facing text. */
function readErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}
