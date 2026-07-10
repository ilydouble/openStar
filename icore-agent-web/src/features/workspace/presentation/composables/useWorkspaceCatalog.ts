import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { AccountPlan } from '../../../account'
import type { ComposerMode, ScenarioTemplate } from '../models/viewModels'

interface ShortcutLocaleRow {
  id: string
  label: string
  role?: string
  summary?: string
  taskPreviews?: string[]
  placeholder?: string
  home?: boolean
}

export interface WorkspaceShortcut extends ComposerMode {
  role: string
  summary: string
  taskPreviews: string[]
  placeholder: string
  home: boolean
}

interface ScenarioTemplateLocaleRow extends ScenarioTemplate {
  starters?: string[]
  accepted?: string[]
}

export interface WorkspaceScenarioTemplate extends ScenarioTemplateLocaleRow {
  label: string
  starters: string[]
  accepted: string[]
}

const UI_BY_ID: Record<string, { emoji: string; panel: string }> = {
  research: { emoji: '🔍', panel: 'bg-gradient-to-br from-rose-100 to-rose-50 border-rose-200/80 dark:from-rose-600/40 dark:to-rose-950/55 dark:border-rose-400/20' },
  code: { emoji: '⚡', panel: 'bg-gradient-to-br from-amber-100 to-amber-50 border-amber-200/80 dark:from-amber-500/35 dark:to-amber-950/55 dark:border-amber-400/20' },
  docs: { emoji: '📄', panel: 'bg-gradient-to-br from-sky-100 to-sky-50 border-sky-200/80 dark:from-sky-500/35 dark:to-sky-950/55 dark:border-sky-400/20' },
  chat: { emoji: '💬', panel: 'bg-gradient-to-br from-violet-100 to-violet-50 border-violet-200/80 dark:from-violet-500/40 dark:to-violet-950/55 dark:border-violet-400/20' },
  image: { emoji: '✨', panel: 'bg-gradient-to-br from-fuchsia-100 to-fuchsia-50 border-fuchsia-200/80 dark:from-fuchsia-500/35 dark:to-fuchsia-950/55 dark:border-fuchsia-400/20' },
  data: { emoji: '📊', panel: 'bg-gradient-to-br from-emerald-100 to-emerald-50 border-emerald-200/80 dark:from-emerald-500/35 dark:to-emerald-950/55 dark:border-emerald-400/20' },
}

const PILL_BY_ID: Record<string, string> = {
  research: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-900/40 dark:text-rose-200 dark:ring-rose-400/30',
  code: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-400/30',
  docs: 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-900/40 dark:text-sky-200 dark:ring-sky-400/30',
  chat: 'bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-900/40 dark:text-violet-200 dark:ring-violet-400/30',
  image: 'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200 dark:bg-fuchsia-900/40 dark:text-fuchsia-200 dark:ring-fuchsia-400/30',
  data: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200 dark:ring-emerald-400/30',
}

export const SHORTCUT_HINT: Record<string, string> = {
  research: 'research',
  code: 'chat',
  docs: 'knowledge',
  chat: 'chat',
  image: 'image',
  data: 'data',
}

/** Build localized workspace shortcuts, templates, and quota view models. */
export function useWorkspaceCatalog(planSummary: Ref<AccountPlan | null>) {
  const { t, tm } = useI18n()
  const translateMessage = tm as unknown as (key: string) => unknown
  const activeShortcutId = ref('')

  const shortcutItems = computed<WorkspaceShortcut[]>(() => {
    const raw = translateMessage('home.shortcuts')
    if (!Array.isArray(raw)) return []
    return raw.filter(isShortcutLocaleRow).map((row) => {
      const ui = UI_BY_ID[row.id] || { emoji: '✨', panel: 'bg-zinc-100 border-zinc-200' }
      return {
        id: row.id,
        label: row.label,
        role: row.role || row.label,
        summary: row.summary || '',
        taskPreviews: Array.isArray(row.taskPreviews) ? row.taskPreviews : [],
        placeholder: row.placeholder || '',
        home: row.home !== false,
        emoji: ui.emoji,
        panel: ui.panel,
      }
    })
  })
  const homeShortcutItems = computed(() => shortcutItems.value.filter((item) => item.home))
  const scenarioTemplates = computed<WorkspaceScenarioTemplate[]>(() => {
    const raw = translateMessage('home.templates')
    if (!Array.isArray(raw)) return []
    const labels = Object.fromEntries(shortcutItems.value.map((item) => [item.id, item.label]))
    return raw.filter(isScenarioTemplateRow).map((row) => ({
      ...row,
      label: labels[row.id] || row.title,
      phases: Array.isArray(row.phases) ? row.phases : [],
      starters: Array.isArray(row.starters) ? row.starters : [],
      accepted: Array.isArray(row.accepted) ? row.accepted : [],
    }))
  })
  const activeShortcut = computed(
    () => shortcutItems.value.find((item) => item.id === activeShortcutId.value) || null,
  )
  const activeScenarioTemplate = computed(
    () => scenarioTemplates.value.find((item) => item.id === activeShortcutId.value) || null,
  )
  const templateLabelById = computed(() =>
    Object.fromEntries(shortcutItems.value.map((item) => [item.id, item.label])),
  )
  const activeShortcutPill = computed<ComposerMode | null>(() => {
    const item = activeShortcut.value
    return item
      ? { id: item.id, label: item.label, emoji: item.emoji, pillClass: PILL_BY_ID[item.id] || '' }
      : null
  })
  const quotaItems = computed(() => {
    const usage = planSummary.value?.usage
    const limits = planSummary.value?.limits
    const items = [
      { label: t('home.quota.tokens'), value: `${usage?.tokens ?? 0}` },
      {
        label: t('home.quota.attachments'),
        value: `${usage?.attachments ?? 0}/${formatLimit(limits?.attachments)}`,
      },
    ]
    if (limits?.tasks !== null && limits?.tasks !== undefined) {
      items.unshift({
        label: t('home.quota.tasks'),
        value: `${usage?.tasks ?? 0}/${formatLimit(limits.tasks)}`,
      })
    }
    return items
  })

  return {
    activeScenarioTemplate,
    activeShortcut,
    activeShortcutId,
    activeShortcutPill,
    homeShortcutItems,
    quotaItems,
    scenarioTemplates,
    shortcutItems,
    templateLabelById,
  }
}

/** Narrow locale content to a valid shortcut row. */
function isShortcutLocaleRow(value: unknown): value is ShortcutLocaleRow {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const row = value as Partial<ShortcutLocaleRow>
  return typeof row.id === 'string' && typeof row.label === 'string'
}

/** Narrow locale content to a valid scenario template row. */
function isScenarioTemplateRow(value: unknown): value is ScenarioTemplateLocaleRow {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const row = value as Partial<ScenarioTemplateLocaleRow>
  return typeof row.id === 'string' && typeof row.title === 'string'
}

/** Render a nullable quota limit. */
function formatLimit(value: number | null | undefined): string | number {
  return value == null ? '∞' : value
}
