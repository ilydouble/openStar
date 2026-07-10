import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { PendingDataFile, PendingImage } from '../models/viewModels'

const MAX_PENDING_IMAGES = 5
const MAX_PENDING_DATA_FILES = 5
const ACCEPTED_EXTENSIONS = new Set([
  '.pdf', '.doc', '.docx', '.txt', '.md',
  '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif',
  '.csv', '.xls', '.xlsx',
])
const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])
const DOCUMENT_EXTENSIONS = new Set([
  '.pdf', '.doc', '.docx', '.txt', '.md', '.csv', '.xls', '.xlsx',
])

/** Manage pending composer image and document files before upload. */
export function usePendingAttachments(onChanged: () => void) {
  const { t } = useI18n()
  const fileInputEl = ref<HTMLInputElement | null>(null)
  const pendingImages = ref<PendingImage[]>([])
  const pendingTrimmedCount = ref(0)
  const pendingDataFiles = ref<PendingDataFile[]>([])
  const pendingDataTrimmedCount = ref(0)
  const isDragging = ref(false)

  /** Return accessible preview text for one pending image. */
  function pendingItemAlt(item: PendingImage): string {
    return item.file.name
      ? t('chat.imageUploadedAlt', { name: item.file.name })
      : t('chat.imageUploadedAltGeneric')
  }

  /** Add image files without exceeding the composer preview limit. */
  function addPendingImageFiles(files: File[] | File): void {
    pendingTrimmedCount.value = 0
    const list = Array.isArray(files) ? files : [files]
    let trimmed = 0
    const next = [...pendingImages.value]
    for (const file of list) {
      if (next.length >= MAX_PENDING_IMAGES) {
        trimmed += 1
        continue
      }
      if (!file.size || !IMAGE_EXTENSIONS.has(fileExtension(file.name))) continue
      next.push({ id: createPendingId(), file, url: URL.createObjectURL(file) })
    }
    pendingImages.value = next
    pendingTrimmedCount.value = trimmed
  }

  /** Remove one pending image and revoke its object URL. */
  function removePendingImageItem(id: string): void {
    const item = pendingImages.value.find((pending) => pending.id === id)
    if (item?.url) URL.revokeObjectURL(item.url)
    pendingImages.value = pendingImages.value.filter((pending) => pending.id !== id)
    if (!pendingImages.value.length) pendingTrimmedCount.value = 0
    resetFileInput()
  }

  /** Clear one or all pending images. */
  function clearPendingImage(id?: string): void {
    if (id) {
      removePendingImageItem(id)
      return
    }
    for (const item of pendingImages.value) URL.revokeObjectURL(item.url)
    pendingImages.value = []
    pendingTrimmedCount.value = 0
    resetFileInput()
  }

  /** Add document files without exceeding the composer preview limit. */
  function addPendingDataFiles(files: File[] | File): void {
    pendingDataTrimmedCount.value = 0
    const list = Array.isArray(files) ? files : [files]
    let trimmed = 0
    const next = [...pendingDataFiles.value]
    for (const file of list) {
      if (next.length >= MAX_PENDING_DATA_FILES) {
        trimmed += 1
        continue
      }
      if (!file.size || !DOCUMENT_EXTENSIONS.has(fileExtension(file.name))) continue
      next.push({ id: createPendingId(), file })
    }
    pendingDataFiles.value = next
    pendingDataTrimmedCount.value = trimmed
  }

  /** Remove one pending document. */
  function removePendingDataFileItem(id: string): void {
    pendingDataFiles.value = pendingDataFiles.value.filter((pending) => pending.id !== id)
    if (!pendingDataFiles.value.length) pendingDataTrimmedCount.value = 0
    resetFileInput()
  }

  /** Clear every pending document. */
  function clearPendingDataFiles(): void {
    pendingDataFiles.value = []
    pendingDataTrimmedCount.value = 0
    resetFileInput()
  }

  /** Add pasted clipboard images to the pending queue. */
  function handlePaste(event: ClipboardEvent): void {
    const items = event.clipboardData?.items
    if (!items?.length) return
    const files: File[] = []
    for (const item of [...items]) {
      if (item.kind !== 'file' || !item.type.startsWith('image/')) continue
      let file = item.getAsFile()
      if (!file?.size) continue
      if (!file.name.trim()) {
        const extension = file.type.split('/')[1] || 'png'
        file = new File([file], `pasted-image.${extension}`, { type: file.type || 'image/png' })
      }
      files.push(file)
    }
    if (!files.length) return
    event.preventDefault()
    addPendingImageFiles(files)
    void nextTick(onChanged)
  }

  /** Classify and add dropped composer files. */
  function handleDrop(event: DragEvent): void {
    isDragging.value = false
    const files = [...(event.dataTransfer?.files || [])]
    if (!files.length) return
    if (files.every((file) => IMAGE_EXTENSIONS.has(fileExtension(file.name)))) {
      addPendingImageFiles(files)
      return
    }
    if (files.every((file) => DOCUMENT_EXTENSIONS.has(fileExtension(file.name)))) {
      addPendingDataFiles(files)
      return
    }
    const file = files[0]
    const extension = fileExtension(file.name)
    if (!ACCEPTED_EXTENSIONS.has(extension)) return
    if (IMAGE_EXTENSIONS.has(extension)) addPendingImageFiles(file)
    else if (DOCUMENT_EXTENSIONS.has(extension)) addPendingDataFiles(file)
  }

  /** Classify and add files selected from the hidden file input. */
  function handleFileSelect(event: Event): void {
    const input = event.currentTarget as HTMLInputElement
    const files = [...(input.files || [])]
    if (files.every((file) => IMAGE_EXTENSIONS.has(fileExtension(file.name)))) {
      addPendingImageFiles(files)
    } else if (files.every((file) => DOCUMENT_EXTENSIONS.has(fileExtension(file.name)))) {
      addPendingDataFiles(files)
    } else if (files[0]) {
      const extension = fileExtension(files[0].name)
      if (IMAGE_EXTENSIONS.has(extension)) addPendingImageFiles(files[0])
      else if (DOCUMENT_EXTENSIONS.has(extension)) addPendingDataFiles(files[0])
    }
    input.value = ''
  }

  /** Reset the file input so the same local file can be selected again. */
  function resetFileInput(): void {
    if (fileInputEl.value) fileInputEl.value.value = ''
  }

  return {
    MAX_PENDING_DATA_FILES,
    MAX_PENDING_IMAGES,
    clearPendingDataFiles,
    clearPendingImage,
    fileInputEl,
    handleDrop,
    handleFileSelect,
    handlePaste,
    isDragging,
    pendingDataFiles,
    pendingDataTrimmedCount,
    pendingImages,
    pendingItemAlt,
    pendingTrimmedCount,
    removePendingDataFileItem,
    removePendingImageItem,
    resetFileInput,
  }
}

/** Return a lowercase filename extension including its dot. */
function fileExtension(name: string): string {
  const index = name.lastIndexOf('.')
  return index >= 0 ? name.slice(index).toLowerCase() : ''
}

/** Create a stable local id for one pending composer file. */
function createPendingId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `pending-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}
