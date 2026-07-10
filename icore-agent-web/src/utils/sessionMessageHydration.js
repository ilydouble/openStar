import enUS from '../shared/i18n/locales/en-US'
import zhCN from '../shared/i18n/locales/zh-CN'
import { getFileDownloadUrl } from '../api/agent.js'
import { resolveUserMessageDisplayContent } from './scenarioPrompt.js'

/** Known auto-generated attachment prompts in every supported locale. */
export function getAutoAttachmentPrompts() {
  const keys = [
    'imageReplyPrompt',
    'imageReplyPromptMulti',
    'fileReplyPrompt',
    'fileReplyPromptMulti',
    'dataReplyPrompt',
    'dataReplyPromptMulti',
    'attachmentsReplyPrompt',
  ]
  const prompts = new Set()
  for (const key of keys) {
    const en = enUS.chat?.[key]
    const zh = zhCN.chat?.[key]
    if (en) prompts.add(en)
    if (zh) prompts.add(zh)
  }
  return prompts
}

/** Build a lookup map from session attachment refs keyed by file UUID. */
export function buildAttachmentLookup(attachments) {
  const map = new Map()
  for (const item of attachments || []) {
    const uuid = String(item?.file_uuid || '').trim()
    if (uuid) map.set(uuid, item)
  }
  return map
}

/** Return whether message content is an auto-generated attachment prompt. */
export function isAutoAttachmentPrompt(content) {
  const text = String(content || '').trim()
  if (!text) return false
  return getAutoAttachmentPrompts().has(text)
}

/** Classify one attachment ref as an image thumbnail or a document chip. */
export function resolveMessageAttachmentKind(ref) {
  const mode = String(ref?.mode || '')
  const contentType = String(ref?.content_type || '')
  if (mode === 'image' || contentType.startsWith('image/')) return 'image'
  return 'data'
}

/** Resolve the user-visible caption for one hydrated attachment message. */
export function resolveAttachmentCaption(rawMessage) {
  const metadata = rawMessage?.metadata
  if (metadata && typeof metadata === 'object') {
    const saved = String(metadata.display_caption || '').trim()
    if (saved) return saved
  }
  const content = String(rawMessage?.content || '').trim()
  if (!content || isAutoAttachmentPrompt(content)) return undefined
  return content
}

/**
 * Return file UUIDs that belong to this message only.
 * Session history may repeat earlier UUIDs on later turns; assign each file once.
 */
export function collectMessageAttachmentUuids(fileUuids, assignedUuids) {
  const messageUuids = []
  for (const rawUuid of fileUuids || []) {
    const uuid = String(rawUuid || '').trim()
    if (!uuid || assignedUuids.has(uuid)) continue
    assignedUuids.add(uuid)
    messageUuids.push(uuid)
  }
  return messageUuids
}

/** Build image/document attachment payloads for one message from its UUID list. */
export function buildMessageAttachmentPayloads(fileUuids, lookup) {
  const images = []
  const dataAttachments = []

  for (const uuid of fileUuids) {
    const ref = lookup.get(uuid)
    if (!ref) continue
    const filename = ref.original_filename || ref.filename || 'file'
    if (resolveMessageAttachmentKind(ref) === 'image') {
      images.push({
        file_uuid: ref.file_uuid,
        content: ref.download_url || '',
        filename,
      })
    } else {
      dataAttachments.push({
        file_uuid: ref.file_uuid,
        filename,
      })
    }
  }

  return { images, dataAttachments }
}

/**
 * Convert persisted session messages plus attachment refs into chat UI messages.
 * @param {{ messages?: Array, attachments?: Array, sessionId: string, templateLabels?: Record<string, string> }} input
 */
export function hydrateSessionMessages({ messages, attachments, sessionId, templateLabels = {} }) {
  const lookup = buildAttachmentLookup(attachments)
  const assignedUuids = new Set()

  return (messages || []).map((msg, index) => {
    const displayContent = msg.role === 'user'
      ? resolveUserMessageDisplayContent(msg, templateLabels)
      : (msg.content || '')

    const base = {
      id: `${sessionId}-${index}-${msg.role}`,
      role: msg.role,
      content: displayContent,
      steps: [],
      stepsCollapsed: true,
      streaming: false,
    }

    if (msg.role !== 'user') return base

    const metadata = msg.metadata && typeof msg.metadata === 'object' ? msg.metadata : {}
    const rawUuids = Array.isArray(metadata.file_uuids) ? metadata.file_uuids : []
    const fileUuids = collectMessageAttachmentUuids(rawUuids, assignedUuids)
    if (!fileUuids.length) return base

    const { images, dataAttachments } = buildMessageAttachmentPayloads(fileUuids, lookup)
    if (!images.length && !dataAttachments.length) return base

    const hasImages = images.length > 0
    const hasData = dataAttachments.length > 0
    const caption = resolveAttachmentCaption(msg)
    let type = 'data'
    if (hasImages && hasData) type = 'composite'
    else if (hasImages) type = 'image'

    return {
      ...base,
      type,
      content: '',
      ...(hasImages ? { images } : {}),
      ...(hasData ? { dataAttachments } : {}),
      ...(caption ? { caption } : {}),
    }
  })
}

/** Refresh expiring image download URLs for hydrated chat messages. */
export async function refreshHydratedImageUrls(messageList) {
  const tasks = []
  for (const msg of messageList || []) {
    if (!msg?.images?.length) continue
    for (const image of msg.images) {
      const fileUuid = String(image?.file_uuid || '').trim()
      if (!fileUuid) continue
      tasks.push(
        getFileDownloadUrl(fileUuid)
          .then((payload) => {
            if (payload?.download_url) image.content = payload.download_url
          })
          .catch(() => {}),
      )
    }
  }
  await Promise.all(tasks)
}
