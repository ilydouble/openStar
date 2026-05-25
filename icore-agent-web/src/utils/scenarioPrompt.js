/** Marker appended by composeScenarioPrompt before template instructions. */
export const SCENARIO_PROMPT_ENVELOPE_MARKERS = [
  '\n---\nYou are acting as an AI operations assistant for a small cross-border business.',
  '\n---\nPlease answer in markdown using this exact section order when it fits the task:',
]

/** Remove template instruction envelope from a persisted user message. */
export function stripScenarioPromptEnvelope(content) {
  const text = String(content || '')
  for (const marker of SCENARIO_PROMPT_ENVELOPE_MARKERS) {
    const index = text.indexOf(marker)
    if (index >= 0) return text.slice(0, index).trim()
  }
  return text.trim()
}

/** Return true when content includes a composed scenario instruction block. */
export function hasScenarioPromptEnvelope(content) {
  const text = String(content || '')
  return SCENARIO_PROMPT_ENVELOPE_MARKERS.some((marker) => text.includes(marker))
}

/**
 * Resolve the user-visible text for one persisted message.
 * @param {{ content?: string, metadata?: { template_id?: string } }} rawMessage
 * @param {Record<string, string>} [templateLabels]
 */
export function resolveUserMessageDisplayContent(rawMessage, templateLabels = {}) {
  const metadata = rawMessage?.metadata
  const templateId = metadata && typeof metadata === 'object'
    ? String(metadata.template_id || '').trim()
    : ''
  if (templateId && templateLabels[templateId]) {
    return templateLabels[templateId]
  }

  const content = String(rawMessage?.content || '').trim()
  if (!content) return ''

  if (hasScenarioPromptEnvelope(content)) {
    return stripScenarioPromptEnvelope(content)
  }

  return content
}

/** Build the agent-only prompt for an active scenario template. */
export function composeScenarioPrompt(message, template) {
  if (!template) return String(message || '').trim()
  const outputSections = (template.outputs || []).map((item) => `- ${item}`).join('\n')
  const phaseSections = (template.phases || []).map((item) => `- ${item}`).join('\n')
  const markdownSections = (template.sections || [])
    .map((item) => `## ${item}\n- Keep this section concise and actionable.`)
    .join('\n\n')
  return [
    String(message || '').trim(),
    '',
    '---',
    'You are acting as an AI operations assistant for a small cross-border business.',
    'Treat this as a task execution draft: explain what you understood, produce structured deliverables, and clearly mark anything that needs human review before execution.',
    '',
    'Execution phases:',
    phaseSections || '- Understand the task\n- Produce an auditable result\n- Recommend next actions',
    '',
    'Please answer in markdown using this exact section order when it fits the task:',
    markdownSections,
    '',
    'Deliverable checklist:',
    outputSections,
  ].join('\n')
}

/** Resolve the compact bubble label for an active template preset. */
export function resolveTemplateBubbleText(templateLabel, fallbackText = '') {
  const label = String(templateLabel || '').trim()
  if (label) return label
  return String(fallbackText || '').trim()
}
