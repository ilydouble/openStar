<template>
  <div class="rounded-[2rem] border border-zinc-200/80 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">{{ t('account.memory.title') }}</p>
        <p class="mt-2 text-sm text-zinc-600 dark:text-zinc-300">{{ t('account.memory.subtitle') }}</p>
      </div>
      <button
        type="button"
        class="inline-flex min-h-10 shrink-0 items-center justify-center rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold transition hover:border-zinc-300 dark:border-white/10 dark:bg-white/[0.04]"
        :disabled="loading"
        @click="loadMemory"
      >
        {{ t('account.memory.refresh') }}
      </button>
    </div>

    <div v-if="loading" class="mt-6 text-sm text-zinc-500 dark:text-zinc-400">
      {{ t('account.memory.loading') }}
    </div>

    <p v-else-if="error" class="mt-6 text-sm text-rose-600 dark:text-rose-300">
      {{ error }}
    </p>

    <div v-else-if="facts.length === 0" class="mt-6 rounded-2xl border border-dashed border-zinc-200 bg-zinc-50 p-5 text-sm text-zinc-500 dark:border-white/10 dark:bg-white/[0.03] dark:text-zinc-400">
      {{ t('account.memory.empty') }}
    </div>

    <div v-else class="mt-6 space-y-6">
      <section
        v-for="category in visibleCategories"
        :key="category"
        class="space-y-3"
      >
        <div class="flex items-center gap-2">
          <h3 class="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
            {{ categoryLabel(category) }}
          </h3>
          <span class="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-600 dark:bg-white/[0.08] dark:text-zinc-300">
            {{ groupedFacts[category]?.length || 0 }}
          </span>
        </div>

        <article
          v-for="fact in visibleFactsForCategory(category)"
          :key="fact.id"
          class="rounded-2xl border border-zinc-200/80 bg-zinc-50 p-4 dark:border-white/10 dark:bg-white/[0.04]"
        >
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0 flex-1">
              <p class="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">
                {{ formatKey(fact.key) }}
              </p>

              <div v-if="editingId === fact.id" class="mt-3 space-y-3">
                <textarea
                  v-model="draftValue"
                  rows="3"
                  maxlength="200"
                  class="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100 dark:border-white/10 dark:bg-white/[0.04] dark:focus:border-violet-300 dark:focus:ring-violet-500/10"
                />
                <div class="flex flex-wrap gap-2">
                  <button
                    type="button"
                    class="rounded-full bg-zinc-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 dark:bg-white dark:text-zinc-950"
                    :disabled="saving || !draftValue.trim()"
                    @click="saveEdit(fact.id)"
                  >
                    {{ t('account.memory.save') }}
                  </button>
                  <button
                    type="button"
                    class="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold dark:border-white/10 dark:bg-white/[0.04]"
                    :disabled="saving"
                    @click="cancelEdit"
                  >
                    {{ t('account.memory.cancel') }}
                  </button>
                </div>
              </div>

              <p v-else class="mt-2 break-words text-sm font-medium text-zinc-900 dark:text-zinc-100">
                {{ fact.value }}
              </p>
            </div>

            <div
              v-if="editingId !== fact.id"
              class="flex shrink-0 flex-wrap gap-2 sm:flex-col sm:items-end"
            >
              <button
                type="button"
                class="rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold dark:border-white/10 dark:bg-white/[0.04]"
                @click="startEdit(fact)"
              >
                {{ t('account.memory.edit') }}
              </button>
              <button
                type="button"
                class="rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300"
                :disabled="deletingId === fact.id"
                @click="confirmDelete(fact.id)"
              >
                {{ t('account.memory.delete') }}
              </button>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-zinc-500 dark:text-zinc-400">
            <span>{{ t('account.memory.confidence') }}: {{ formatConfidence(fact.confidence) }}</span>
            <span>{{ t('account.memory.lastConfirmed') }}: {{ formatDate(fact.last_confirmed_at) }}</span>
          </div>
        </article>

        <button
          v-if="categoryHasMore(category)"
          type="button"
          class="inline-flex min-h-9 items-center rounded-full border border-zinc-200 bg-white px-4 py-2 text-xs font-semibold text-zinc-700 transition hover:border-zinc-300 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-200"
          @click="toggleCategoryExpanded(category)"
        >
          {{
            isCategoryExpanded(category)
              ? t('account.memory.showLess')
              : t('account.memory.showMore', { count: hiddenFactCount(category) })
          }}
        </button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteMemoryFact, fetchMemory, updateMemoryFact } from '../api/account.js'

const { t, locale } = useI18n()

const CATEGORY_ORDER = ['personal', 'work_context', 'goal', 'preference', 'constraint']
const CATEGORY_PREVIEW_LIMIT = 3

const loading = ref(true)
const saving = ref(false)
const deletingId = ref(null)
const error = ref('')
const facts = ref([])
const editingId = ref(null)
const draftValue = ref('')
const expandedCategories = ref({})

const groupedFacts = computed(() => {
  const groups = Object.fromEntries(CATEGORY_ORDER.map((category) => [category, []]))
  for (const fact of facts.value) {
    const category = CATEGORY_ORDER.includes(fact.category) ? fact.category : 'preference'
    groups[category].push(fact)
  }
  return groups
})

const visibleCategories = computed(() =>
  CATEGORY_ORDER.filter((category) => (groupedFacts.value[category]?.length || 0) > 0),
)

/** Return all facts for one category group. */
function factsForCategory(category) {
  return groupedFacts.value[category] || []
}

/** Return whether a category group is expanded beyond the preview limit. */
function isCategoryExpanded(category) {
  return Boolean(expandedCategories.value[category])
}

/** Toggle expanded state for one category group. */
function toggleCategoryExpanded(category) {
  expandedCategories.value = {
    ...expandedCategories.value,
    [category]: !expandedCategories.value[category],
  }
}

/** Return whether a category has more facts than the preview limit. */
function categoryHasMore(category) {
  return factsForCategory(category).length > CATEGORY_PREVIEW_LIMIT
}

/** Return how many facts are hidden in one collapsed category. */
function hiddenFactCount(category) {
  return Math.max(factsForCategory(category).length - CATEGORY_PREVIEW_LIMIT, 0)
}

/** Return the facts visible for one category based on expand state. */
function visibleFactsForCategory(category) {
  const items = factsForCategory(category)
  if (isCategoryExpanded(category) || items.length <= CATEGORY_PREVIEW_LIMIT) {
    return items
  }
  return items.slice(0, CATEGORY_PREVIEW_LIMIT)
}

/** Load active memory facts for the account memory manager. */
async function loadMemory() {
  loading.value = true
  error.value = ''
  expandedCategories.value = {}
  try {
    const payload = await fetchMemory()
    facts.value = Array.isArray(payload?.facts) ? payload.facts : []
  } catch (err) {
    error.value = err?.message || t('account.memory.loadFailed')
    facts.value = []
  } finally {
    loading.value = false
  }
}

/** Return a localized label for one memory category. */
function categoryLabel(category) {
  const key = `account.memory.categories.${category}`
  return t(key)
}

/** Render a snake_case fact key for display. */
function formatKey(key) {
  return String(key || '').replace(/_/g, ' ')
}

/** Format confidence as a whole-number percentage. */
function formatConfidence(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

/** Format a unix timestamp for the active locale. */
function formatDate(timestamp) {
  const seconds = Number(timestamp)
  if (!seconds) return '-'
  const date = new Date(seconds * 1000)
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date)
}

/** Begin inline editing for one fact. */
function startEdit(fact) {
  editingId.value = fact.id
  draftValue.value = fact.value
}

/** Cancel inline editing. */
function cancelEdit() {
  editingId.value = null
  draftValue.value = ''
}

/** Persist an edited fact value. */
async function saveEdit(factId) {
  const value = draftValue.value.trim()
  if (!value) return
  saving.value = true
  error.value = ''
  try {
    const updated = await updateMemoryFact(factId, value)
    facts.value = facts.value.map((fact) => (fact.id === factId ? { ...fact, ...updated } : fact))
    cancelEdit()
  } catch (err) {
    error.value = err?.message || t('account.memory.saveFailed')
  } finally {
    saving.value = false
  }
}

/** Delete one fact after confirmation. */
async function confirmDelete(factId) {
  if (!window.confirm(t('account.memory.deleteConfirm'))) return
  deletingId.value = factId
  error.value = ''
  try {
    await deleteMemoryFact(factId)
    facts.value = facts.value.filter((fact) => fact.id !== factId)
    if (editingId.value === factId) cancelEdit()
  } catch (err) {
    error.value = err?.message || t('account.memory.deleteFailed')
  } finally {
    deletingId.value = null
  }
}

onMounted(loadMemory)
</script>
