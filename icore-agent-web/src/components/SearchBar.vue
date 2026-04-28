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
      <!-- 待发送图片：ChatGPT 式 — 左侧小方缩略图 + 角标关闭，整体 inline 不占满宽 -->
      <div v-if="pendingImage" class="mb-2 flex w-full justify-start">
        <div
          class="inline-flex max-w-[calc(100%-0.5rem)] items-center gap-2.5 rounded-xl border border-zinc-200/90 bg-zinc-50/95 py-1 pl-1 pr-2.5 shadow-sm dark:border-white/[0.1] dark:bg-zinc-800/95 dark:shadow-none"
          :title="`${pendingImage.file.name} — ${t('chat.pendingImageHint')}`"
        >
          <div
            class="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-zinc-200 dark:bg-zinc-950"
          >
            <img
              :src="pendingImage.url"
              :alt="pendingImageAlt"
              class="pointer-events-none h-full w-full object-cover"
              draggable="false"
            />
            <button
              type="button"
              class="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/55 text-white shadow-sm ring-1 ring-white/15 backdrop-blur-[1px] transition hover:bg-black/75 dark:bg-black/60 dark:ring-white/10"
              :aria-label="t('home.chatInput.removePendingImage')"
              @click.stop="clearPendingImage"
            >
              <svg class="h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="min-w-0 max-w-[11rem] py-0.5 leading-tight sm:max-w-[13.5rem]">
            <p
              class="truncate text-xs font-medium text-zinc-800 dark:text-zinc-100"
              :title="pendingImage.file.name"
            >
              {{ pendingImage.file.name }}
            </p>
            <p class="truncate text-[10px] text-zinc-500 dark:text-zinc-400" :title="`${t('chat.imageMessageLabel')} — ${t('chat.pendingImageHint')}`">
              <span class="font-medium text-zinc-600 dark:text-zinc-300">{{ t('chat.imageMessageLabel') }}</span>
              <span class="text-zinc-400 dark:text-zinc-500"> — </span>
              <span>{{ t('chat.pendingImageHint') }}</span>
            </p>
          </div>
        </div>
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
              @click.stop="plusMenuOpen = !plusMenuOpen"
            >
              <Plus class="h-5 w-5" stroke-width="2" />
            </button>

            <!-- 隐藏的文件输入 -->
            <input
              ref="fileInputEl"
              type="file"
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
                class="absolute bottom-full left-0 z-[100] mb-2 max-h-[min(22rem,calc(100dvh-6rem))] min-w-[15rem]
                       max-w-[min(17rem,calc(100vw-2rem))] origin-bottom-left overflow-y-auto overflow-x-hidden
                       rounded-xl border border-zinc-200/90 bg-white/95 py-1 shadow-xl shadow-zinc-900/15
                       backdrop-blur-md dark:border-white/10 dark:bg-zinc-900/95 dark:shadow-black/50"
                role="menu"
              >
                <button
                  v-for="item in plusMenuItems"
                  :key="item.labelKey"
                  type="button"
                  role="menuitem"
                  class="group flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm
                         text-zinc-900 transition-all duration-200
                         hover:bg-zinc-100/90
                         dark:text-white dark:hover:bg-white/10"
                  @click="handleMenuItemClick(item)"
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
  User,
  Paperclip,
  Image,
  Brain,
  Search,
  Mic,
  SendHorizontal,
} from 'lucide-vue-next'

const TEXTAREA_MAX_HEIGHT = 200

const { t } = useI18n()

const props = defineProps({
  placeholder: { type: String, default: '' },
  modePill: { type: Object, default: null },
  /** 正在接收助手流式回复：主按钮切换为「停止」 */
  streaming: { type: Boolean, default: false },
  /** 上传等场景下禁止发起新一轮发送（非流式阶段） */
  sendBlocked: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'file-selected', 'clear-mode', 'stop'])

const input = ref('')
const area = ref(null)
const fileInputEl = ref(null)
const plusMenuOpen = ref(false)
const plusRootRef = ref(null)
const isDragging = ref(false)

/** @type {import('vue').Ref<{ file: File, url: string } | null>} */
const pendingImage = ref(null)

/** 流式输出时可点停止；否则无内容且无图时禁用发送 */
const mainActionDisabled = computed(
  () =>
    !props.streaming
    && (props.sendBlocked || (!input.value.trim() && !pendingImage.value)),
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

/** Ctrl+V / 剪贴板图片 → 与「选择图片」相同的待发送预览 */
function onPaste(e) {
  const cd = e.clipboardData
  if (!cd?.items?.length) return
  const imageItems = [...cd.items].filter(
    (it) => it.kind === 'file' && typeof it.type === 'string' && it.type.startsWith('image/'),
  )
  if (!imageItems.length) return
  let file = imageItems[0].getAsFile()
  if (!file?.size) return
  if (!file.name?.trim()) {
    const ext = file.type?.split('/')[1] || 'png'
    file = new File([file], `pasted-image.${ext}`, { type: file.type || 'image/png' })
  }
  e.preventDefault()
  setPendingImage(file)
  nextTick(autoGrow)
}

const ACCEPTED_EXTS = new Set([
  '.pdf', '.docx', '.txt', '.md',
  '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif',
  '.csv', '.xls', '.xlsx',
])

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])

function extOf(name) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

const pendingImageAlt = computed(() => {
  const f = pendingImage.value?.file
  if (!f?.name) return t('chat.imageUploadedAltGeneric')
  return t('chat.imageUploadedAlt', { name: f.name })
})

function setPendingImage(file) {
  if (pendingImage.value?.url) {
    URL.revokeObjectURL(pendingImage.value.url)
  }
  pendingImage.value = { file, url: URL.createObjectURL(file) }
}

function clearPendingImage() {
  if (pendingImage.value?.url) {
    URL.revokeObjectURL(pendingImage.value.url)
  }
  pendingImage.value = null
  if (fileInputEl.value) fileInputEl.value.value = ''
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  const ext = extOf(file.name)
  if (!ACCEPTED_EXTS.has(ext)) return
  if (IMAGE_EXTS.has(ext)) {
    setPendingImage(file)
    return
  }
  emit('file-selected', file)
}

const plusMenuItems = [
  { icon: User,      labelKey: 'home.chatInput.selectAgent',    action: null },
  { icon: Paperclip, labelKey: 'home.chatInput.addFileOrPhoto', action: 'openFile' },
  { icon: Image,     labelKey: 'home.chatInput.createImage',    action: null },
  { icon: Brain,     labelKey: 'home.chatInput.thinkDeeply',    action: null },
  { icon: Search,    labelKey: 'home.chatInput.searchInternet', action: null },
]

function closePlusMenu() {
  plusMenuOpen.value = false
}

function handleMenuItemClick(item) {
  closePlusMenu()
  if (item.action === 'openFile') {
    // 重置 value 使得同一文件可重复选
    if (fileInputEl.value) fileInputEl.value.value = ''
    fileInputEl.value?.click()
  }
}

function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const ext = extOf(file.name)
  if (IMAGE_EXTS.has(ext)) {
    setPendingImage(file)
  } else {
    emit('file-selected', file)
  }
  // 重置让用户可以再次选同名文件
  e.target.value = ''
}

function onDocumentClick(e) {
  if (plusRootRef.value && !plusRootRef.value.contains(e.target)) {
    plusMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  nextTick(autoGrow)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  clearPendingImage()
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
  const file = pendingImage.value?.file ?? null
  if (!msg && !file) return
  // Reset composer *before* emit so preview clears immediately even if the parent
  // handler is async and the runtime waits on its returned Promise.
  input.value = ''
  clearPendingImage()
  emit('submit', { message: msg, imageFile: file })
  nextTick(autoGrow)
}

defineExpose({
  focus: () => area.value?.focus(),
  clearPendingImage,
})
</script>
