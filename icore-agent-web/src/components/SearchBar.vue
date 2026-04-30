<template>
  <div class="relative z-0 mx-auto w-full max-w-3xl">
    <div
      :class="[
        'relative z-0 rounded-2xl border p-3 shadow-sm backdrop-blur-md transition-all duration-200',
        'hover:shadow-md focus-within:border-zinc-300/90 focus-within:shadow-md',
        isDragging
          ? 'border-violet-400 bg-violet-50/80 shadow-md dark:border-violet-400/60 dark:bg-violet-900/20'
          : 'border-zinc-200/80 bg-white/90 dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl dark:focus-within:border-white/20',
      ]"
      @dragover.prevent="isDragging = true"
      @dragleave.self="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <!-- 拖拽提示覆盖层 -->
      <div
        v-if="isDragging"
        class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-2xl"
      >
        <span class="text-sm font-medium text-violet-600 dark:text-violet-300">{{ t('home.chatInput.dropToUpload') }}</span>
      </div>
      <!-- 模式 pill -->
      <div v-if="modePill" class="mb-2 flex flex-wrap items-center gap-2">
        <span
          :class="[
            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1',
            modePill.pillClass || 'bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-900/40 dark:text-violet-200 dark:ring-violet-400/30',
          ]"
        >
          <span>{{ modePill.emoji }}</span>
          <span>{{ modePill.label }}{{ t('home.modePill.suffix') }}</span>
          <button
            type="button"
            :aria-label="t('home.modePill.clear')"
            class="-mr-0.5 ml-0.5 rounded-full p-0.5 opacity-70 transition hover:bg-black/10 hover:opacity-100 dark:hover:bg-white/10"
            @click="$emit('clear-mode')"
          >
            <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </span>
      </div>
      <!-- 待发送图片：紧凑方形缩略图横排/换行（与气泡内样式一致） -->
      <div v-if="pendingImages.length" class="mb-2 flex flex-col gap-1">
        <div class="flex flex-wrap items-center gap-1.5">
          <div
            v-for="item in pendingImages"
            :key="item.id"
            :title="item.file.name"
            class="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-zinc-200/90 shadow-sm ring-1 ring-zinc-200/80 dark:bg-zinc-800 dark:ring-white/10"
          >
            <img
              :src="item.url"
              :alt="pendingItemAlt(item)"
              class="h-full w-full object-cover"
              draggable="false"
              loading="lazy"
            />
            <button
              type="button"
              class="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-zinc-950/70 text-white shadow-sm ring-1 ring-white/25 backdrop-blur-[2px] transition hover:bg-zinc-950/90 dark:bg-black/65 dark:ring-white/20 dark:hover:bg-black/85"
              :aria-label="t('home.chatInput.removePendingImage')"
              @click.stop="removePendingImageItem(item.id)"
            >
              <span class="text-xs font-light leading-none" aria-hidden="true">×</span>
            </button>
          </div>
        </div>
        <p class="text-[11px] leading-tight text-zinc-500 dark:text-zinc-500">
          {{ t('chat.pendingImagesCount', { n: pendingImages.length, max: MAX_PENDING_IMAGES }) }}
        </p>
        <p v-if="pendingTrimmedCount > 0" class="text-[11px] leading-tight text-amber-700 dark:text-amber-400/90">
          {{ t('chat.pendingImagesTrimmed', { n: pendingTrimmedCount, max: MAX_PENDING_IMAGES }) }}
        </p>
      </div>
      <!-- 待发送数据文件（CSV / Excel）：与图片一致的「先发预览、发送后进气泡」 -->
      <div v-if="pendingDataFiles.length" class="mb-2 flex flex-col gap-1">
        <div class="flex flex-wrap items-center gap-1.5">
          <div
            v-for="item in pendingDataFiles"
            :key="item.id"
            :title="item.file.name"
            class="relative flex h-14 max-w-[11rem] shrink-0 items-center gap-2 rounded-lg border border-zinc-200/90 bg-zinc-50 px-2.5 shadow-sm ring-1 ring-zinc-200/70 dark:border-white/10 dark:bg-zinc-800/80 dark:ring-white/10"
          >
            <svg class="h-7 w-7 shrink-0 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span class="min-w-0 flex-1 truncate text-[11px] font-medium leading-tight text-zinc-800 dark:text-zinc-200">
              {{ item.file.name }}
            </span>
            <button
              type="button"
              class="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-zinc-950/70 text-white shadow-sm ring-1 ring-white/25 backdrop-blur-[2px] transition hover:bg-zinc-950/90 dark:bg-black/65 dark:ring-white/20 dark:hover:bg-black/85"
              :aria-label="t('chat.removePendingDataFile')"
              @click.stop="removePendingDataFileItem(item.id)"
            >
              <span class="text-xs font-light leading-none" aria-hidden="true">×</span>
            </button>
          </div>
        </div>
        <p class="text-[11px] leading-tight text-zinc-500 dark:text-zinc-500">
          {{ t('chat.pendingDataFilesCount', { n: pendingDataFiles.length, max: MAX_PENDING_DATA_FILES }) }}
        </p>
        <p v-if="pendingDataTrimmedCount > 0" class="text-[11px] leading-tight text-amber-700 dark:text-amber-400/90">
          {{ t('chat.pendingDataFilesTrimmed', { n: pendingDataTrimmedCount, max: MAX_PENDING_DATA_FILES }) }}
        </p>
      </div>
      <div class="flex items-center">
        <div class="flex shrink-0 items-center">
          <div ref="plusRootRef" class="relative z-10">
            <button
              type="button"
              aria-haspopup="menu"
              :aria-expanded="plusMenuOpen"
              class="flex h-9 w-9 items-center justify-center rounded-xl border border-zinc-200/80
                     bg-zinc-50/90 text-zinc-700 backdrop-blur-sm transition-all duration-200
                     hover:border-zinc-300 hover:bg-zinc-100/90 hover:text-zinc-900
                     active:scale-95
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/30
                     dark:border-white/10 dark:bg-white/10 dark:text-white
                     dark:hover:border-white/20 dark:hover:bg-white/[0.14]"
              @click.stop="togglePlusMenu"
            >
              <Plus class="h-5 w-5" stroke-width="2" />
            </button>

            <!-- 隐藏的文件输入 -->
            <input
              ref="fileInputEl"
              type="file"
              multiple
              class="hidden"
              accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png,.webp,.bmp,.gif,.csv,.xls,.xlsx"
              @change="handleFileSelect"
            />

            <Transition
              enter-active-class="transition duration-200 ease-out"
              enter-from-class="scale-95 opacity-0"
              enter-to-class="scale-100 opacity-100"
              leave-active-class="transition duration-150 ease-in"
              leave-from-class="scale-100 opacity-100"
              leave-to-class="scale-95 opacity-0"
            >
              <div
                v-show="plusMenuOpen"
                class="absolute bottom-full left-0 z-[100] mb-2 max-h-[min(24rem,calc(100dvh-6rem))] min-w-[15rem]
                       max-w-[min(18.5rem,calc(100vw-2rem))] origin-bottom-left overflow-y-auto overflow-x-hidden
                       rounded-xl border border-zinc-200/90 bg-white/95 py-1 shadow-xl shadow-zinc-900/15
                       backdrop-blur-md dark:border-white/10 dark:bg-zinc-900/95 dark:shadow-black/50"
                role="menu"
              >
                <template v-if="modePickerOpen && modeMenuItemsList.length">
                  <button
                    type="button"
                    class="flex w-full items-center gap-2 border-b border-zinc-200/80 px-3 py-2 text-left text-sm text-zinc-600 transition-colors
                           hover:bg-zinc-100/90 hover:text-zinc-900 dark:border-white/10 dark:text-zinc-400 dark:hover:bg-white/10 dark:hover:text-zinc-200"
                    @click.stop="modePickerOpen = false"
                  >
                    <ChevronLeft class="h-4 w-4 shrink-0" stroke-width="2" aria-hidden="true" />
                    {{ t('home.chatInput.modePickerBack') }}
                  </button>
                  <button
                    v-for="m in modeMenuItemsList"
                    :key="m.id"
                    type="button"
                    role="menuitem"
                    :aria-pressed="activeModeId === m.id"
                    class="group flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm transition-colors duration-200
                           text-zinc-900 hover:bg-zinc-100/90 dark:text-white dark:hover:bg-white/10"
                    :class="activeModeId === m.id ? 'bg-violet-50/90 dark:bg-violet-950/35' : ''"
                    @click.stop="selectComposerMode(m.id)"
                  >
                    <span
                      :class="[
                        'flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border text-base shadow-md ring-1 transition-all duration-200 sm:text-lg',
                        m.panel,
                        activeModeId === m.id
                          ? 'ring-2 ring-violet-500 ring-offset-2 ring-offset-white dark:ring-violet-400 dark:ring-offset-zinc-900'
                          : 'ring-black/5 group-hover:ring-black/10 dark:ring-white/10 dark:group-hover:ring-white/15',
                      ]"
                    >{{ m.emoji }}</span>
                    <span class="min-w-0 flex-1 font-medium leading-tight">{{ m.label }}</span>
                  </button>
                </template>
                <template v-else>
                  <button
                    v-for="item in plusMenuItems"
                    :key="item.labelKey"
                    type="button"
                    role="menuitem"
                    class="group flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm
                           text-zinc-900 transition-all duration-200
                           hover:bg-zinc-100/90
                           dark:text-white dark:hover:bg-white/10"
                    @click.stop="handleMenuItemClick(item)"
                  >
                    <component
                      :is="item.icon"
                      class="h-4 w-4 shrink-0 text-zinc-500 transition-colors duration-200
                             group-hover:text-zinc-900
                             dark:text-zinc-400 dark:group-hover:text-white"
                      stroke-width="2"
                    />
                    {{ t(item.labelKey) }}
                  </button>
                </template>
              </div>
            </Transition>
          </div>
        </div>

        <div class="flex min-w-0 flex-1 items-center px-3">
          <textarea
            ref="area"
            v-model="input"
            rows="1"
            :placeholder="placeholder || t('home.inputPlaceholder')"
            class="box-border min-h-[2.25rem] w-full resize-none appearance-none overflow-hidden
                   rounded-xl border border-transparent bg-transparent px-0 py-1.5 text-sm leading-6
                   text-zinc-900 outline-none [-ms-overflow-style:none] [scrollbar-width:none]
                   placeholder:text-transparent sm:placeholder:text-zinc-400
                   dark:text-white dark:placeholder:text-transparent dark:sm:placeholder:text-zinc-500
                   [&::-webkit-scrollbar]:hidden"
            @keydown.enter.exact.prevent="onEnterInTextarea"
            @input="autoGrow"
            @paste="onPaste"
          />
        </div>

        <div class="flex shrink-0 items-center gap-2">
          <button
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-full
                   text-zinc-500 transition-all duration-200
                   hover:bg-zinc-100/90 hover:text-zinc-900
                   active:scale-90
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/30
                   dark:text-zinc-400 dark:hover:bg-white/10 dark:hover:text-white"
          >
            <Mic class="h-[1.125rem] w-[1.125rem]" stroke-width="2" />
          </button>

          <button
            type="button"
            :disabled="mainActionDisabled"
            :class="[
              'group flex h-9 w-9 items-center justify-center rounded-full shadow-sm transition-all duration-200 active:scale-90',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/30',
              streaming
                ? 'bg-zinc-900 text-white hover:bg-red-600 hover:shadow-md hover:ring-2 hover:ring-red-500/40 dark:bg-white dark:text-zinc-900 dark:hover:bg-red-500 dark:hover:text-white dark:hover:ring-red-400/50'
                : 'bg-zinc-900 text-white hover:bg-zinc-800 hover:shadow dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-100',
              mainActionDisabled ? 'pointer-events-none opacity-30 shadow-none' : '',
            ]"
            :aria-label="streaming ? t('chat.stopGenerating') : t('chat.sendMessage')"
            :title="streaming ? t('chat.stopHint') : t('chat.sendMessage')"
            @click="onMainAction"
          >
            <span
              v-if="streaming"
              class="block h-2.5 w-2.5 shrink-0 rounded-[3px] bg-white shadow-sm group-hover:bg-white dark:bg-zinc-900 dark:shadow-none dark:group-hover:bg-white"
              aria-hidden="true"
            />
            <SendHorizontal
              v-else
              class="h-[1.125rem] w-[1.125rem]"
              stroke-width="2"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Plus,
  Paperclip,
  Image,
  Brain,
  Search,
  Mic,
  SendHorizontal,
  LayoutGrid,
  ChevronLeft,
} from 'lucide-vue-next'

const TEXTAREA_MAX_HEIGHT = 200

const { t } = useI18n()

const props = defineProps({
  placeholder: { type: String, default: '' },
  modePill: { type: Object, default: null },
  /** 与首页快捷方式同源：id / label / emoji / panel */
  modeMenuItems: { type: Array, default: () => [] },
  activeModeId: { type: String, default: '' },
  /** 正在接收助手流式回复：主按钮切换为「停止」 */
  streaming: { type: Boolean, default: false },
  /** 上传等场景下禁止发起新一轮发送（非流式阶段） */
  sendBlocked: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'file-selected', 'clear-mode', 'stop', 'select-mode'])

const modeMenuItemsList = computed(() =>
  Array.isArray(props.modeMenuItems) ? props.modeMenuItems : [],
)

const input = ref('')
const area = ref(null)
const fileInputEl = ref(null)
const plusMenuOpen = ref(false)
const modePickerOpen = ref(false)
const plusRootRef = ref(null)
const isDragging = ref(false)

const MAX_PENDING_IMAGES = 5
const MAX_PENDING_DATA_FILES = 5

/** @type {import('vue').Ref<Array<{ id: string, file: File, url: string }>>} */
const pendingImages = ref([])
/** 最近一次批量选择时因上限丢弃的张数（展示提示后于下次添加时清零） */
const pendingTrimmedCount = ref(0)

/** @type {import('vue').Ref<Array<{ id: string, file: File }>>} */
const pendingDataFiles = ref([])
const pendingDataTrimmedCount = ref(0)

/** 流式输出时可点停止；否则无内容、无图且无数据文件时禁用发送 */
const mainActionDisabled = computed(
  () =>
    !props.streaming
    && (props.sendBlocked
      || (!input.value.trim() && !pendingImages.value.length && !pendingDataFiles.value.length)),
)

function onMainAction() {
  if (props.streaming) {
    emit('stop')
    return
  }
  handleSubmit()
}

function onEnterInTextarea() {
  if (props.streaming) return
  handleSubmit()
}

/** Ctrl+V / 剪贴板图片 → 与「选择图片」相同的待发送预览（支持多张） */
function onPaste(e) {
  const cd = e.clipboardData
  if (!cd?.items?.length) return
  const imageItems = [...cd.items].filter(
    (it) => it.kind === 'file' && typeof it.type === 'string' && it.type.startsWith('image/'),
  )
  if (!imageItems.length) return
  const files = []
  for (const it of imageItems) {
    let file = it.getAsFile()
    if (!file?.size) continue
    if (!file.name?.trim()) {
      const ext = file.type?.split('/')[1] || 'png'
      file = new File([file], `pasted-image.${ext}`, { type: file.type || 'image/png' })
    }
    files.push(file)
  }
  if (!files.length) return
  e.preventDefault()
  addPendingImageFiles(files)
  nextTick(autoGrow)
}

const ACCEPTED_EXTS = new Set([
  '.pdf', '.docx', '.txt', '.md',
  '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif',
  '.csv', '.xls', '.xlsx',
])

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])
const DATA_EXTS = new Set(['.csv', '.xls', '.xlsx'])

function extOf(name) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

function makePendingId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `pi-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function pendingItemAlt(item) {
  const f = item?.file
  if (!f?.name) return t('chat.imageUploadedAltGeneric')
  return t('chat.imageUploadedAlt', { name: f.name })
}

/** 将图片文件加入待发送列表（总数不超过 MAX_PENDING_IMAGES） */
function addPendingImageFiles(files) {
  pendingTrimmedCount.value = 0
  const list = Array.isArray(files) ? files : [files]
  let trimmed = 0
  const next = [...pendingImages.value]
  for (const file of list) {
    if (next.length >= MAX_PENDING_IMAGES) {
      trimmed += 1
      continue
    }
    if (!file?.size) continue
    const ext = extOf(file.name)
    if (!IMAGE_EXTS.has(ext)) continue
    next.push({
      id: makePendingId(),
      file,
      url: URL.createObjectURL(file),
    })
  }
  pendingImages.value = next
  if (trimmed > 0) pendingTrimmedCount.value = trimmed
}

function removePendingImageItem(id) {
  const item = pendingImages.value.find((p) => p.id === id)
  if (item?.url) URL.revokeObjectURL(item.url)
  pendingImages.value = pendingImages.value.filter((p) => p.id !== id)
  if (!pendingImages.value.length) pendingTrimmedCount.value = 0
  if (fileInputEl.value) fileInputEl.value.value = ''
}

function clearPendingImage() {
  for (const p of pendingImages.value) {
    if (p.url) URL.revokeObjectURL(p.url)
  }
  pendingImages.value = []
  pendingTrimmedCount.value = 0
  if (fileInputEl.value) fileInputEl.value.value = ''
}

/** 待发送数据文件加入列表（总数不超过 MAX_PENDING_DATA_FILES） */
function addPendingDataFiles(files) {
  pendingDataTrimmedCount.value = 0
  const list = Array.isArray(files) ? files : [files]
  let trimmed = 0
  const next = [...pendingDataFiles.value]
  for (const file of list) {
    if (next.length >= MAX_PENDING_DATA_FILES) {
      trimmed += 1
      continue
    }
    if (!file?.size) continue
    const ext = extOf(file.name)
    if (!DATA_EXTS.has(ext)) continue
    next.push({ id: makePendingId(), file })
  }
  pendingDataFiles.value = next
  if (trimmed > 0) pendingDataTrimmedCount.value = trimmed
}

function removePendingDataFileItem(id) {
  pendingDataFiles.value = pendingDataFiles.value.filter((p) => p.id !== id)
  if (!pendingDataFiles.value.length) pendingDataTrimmedCount.value = 0
  if (fileInputEl.value) fileInputEl.value.value = ''
}

function clearPendingDataFiles() {
  pendingDataFiles.value = []
  pendingDataTrimmedCount.value = 0
  if (fileInputEl.value) fileInputEl.value.value = ''
}

function handleDrop(e) {
  isDragging.value = false
  const raw = e.dataTransfer?.files
  if (!raw?.length) return
  const files = [...raw]
  const allImages = files.length > 0 && files.every((f) => IMAGE_EXTS.has(extOf(f.name)))
  if (allImages) {
    addPendingImageFiles(files)
    return
  }
  const allData = files.length > 0 && files.every((f) => DATA_EXTS.has(extOf(f.name)))
  if (allData) {
    addPendingDataFiles(files)
    return
  }
  const file = files[0]
  const ext = extOf(file.name)
  if (!ACCEPTED_EXTS.has(ext)) return
  if (IMAGE_EXTS.has(ext)) {
    addPendingImageFiles([file])
    return
  }
  if (DATA_EXTS.has(ext)) {
    addPendingDataFiles([file])
    return
  }
  emit('file-selected', file)
}

const plusMenuItems = [
  { icon: LayoutGrid, labelKey: 'home.chatInput.selectMode', action: 'openModePicker' },
  { icon: Paperclip, labelKey: 'home.chatInput.addFileOrPhoto', action: 'openFile' },
  { icon: Image,     labelKey: 'home.chatInput.createImage',    action: null },
  { icon: Brain,     labelKey: 'home.chatInput.thinkDeeply',    action: null },
  { icon: Search,    labelKey: 'home.chatInput.searchInternet', action: null },
]

function closePlusMenu() {
  plusMenuOpen.value = false
  modePickerOpen.value = false
}

function togglePlusMenu() {
  if (plusMenuOpen.value) {
    closePlusMenu()
  } else {
    modePickerOpen.value = false
    plusMenuOpen.value = true
  }
}

function handleMenuItemClick(item) {
  if (item.action === 'openModePicker') {
    if (!modeMenuItemsList.value.length) return
    modePickerOpen.value = true
    return
  }
  closePlusMenu()
  if (item.action === 'openFile') {
    // 重置 value 使得同一文件可重复选
    if (fileInputEl.value) fileInputEl.value.value = ''
    fileInputEl.value?.click()
  }
}

function selectComposerMode(id) {
  emit('select-mode', id)
  closePlusMenu()
  nextTick(() => area.value?.focus())
}

function handleFileSelect(e) {
  const files = [...(e.target.files || [])]
  if (!files.length) return
  const allImages = files.length > 0 && files.every((f) => IMAGE_EXTS.has(extOf(f.name)))
  if (allImages) {
    addPendingImageFiles(files)
  } else {
    const allData = files.length > 0 && files.every((f) => DATA_EXTS.has(extOf(f.name)))
    if (allData) {
      addPendingDataFiles(files)
    } else {
      const file = files[0]
      const ext = extOf(file.name)
      if (IMAGE_EXTS.has(ext)) {
        addPendingImageFiles([file])
      } else if (DATA_EXTS.has(ext)) {
        addPendingDataFiles([file])
      } else {
        emit('file-selected', file)
      }
    }
  }
  e.target.value = ''
}

function onDocumentClick(e) {
  if (plusRootRef.value && !plusRootRef.value.contains(e.target)) {
    closePlusMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  nextTick(autoGrow)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  clearPendingImage()
  clearPendingDataFiles()
})

function autoGrow() {
  const el = area.value
  if (!el) return
  el.style.overflow = 'hidden'
  el.style.height = 'auto'
  void el.offsetHeight
  el.style.height = `${Math.min(el.scrollHeight, TEXTAREA_MAX_HEIGHT)}px`
}

function handleSubmit() {
  const msg = input.value.trim()
  const imageFiles = pendingImages.value.map((p) => p.file)
  const dataFiles = pendingDataFiles.value.map((p) => p.file)
  if (!msg && !imageFiles.length && !dataFiles.length) return
  input.value = ''
  clearPendingImage()
  clearPendingDataFiles()
  emit('submit', { message: msg, imageFiles, dataFiles })
  nextTick(autoGrow)
}

defineExpose({
  focus: () => area.value?.focus(),
  clearPendingImage,
  clearPendingDataFiles,
})
</script>
