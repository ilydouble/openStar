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
        <span class="text-sm font-medium text-violet-600 dark:text-violet-300">松开鼠标上传文件</span>
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
            @keydown.enter.exact.prevent="handleSubmit"
            @input="autoGrow"
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
            :disabled="!input.trim()"
            class="flex h-9 w-9 items-center justify-center rounded-full
                   bg-zinc-900 text-white shadow-sm transition-all duration-200
                   hover:bg-zinc-800 hover:shadow
                   active:scale-90
                   disabled:pointer-events-none disabled:opacity-30 disabled:shadow-none
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/30
                   dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-100"
            @click="handleSubmit"
          >
            <SendHorizontal class="h-[1.125rem] w-[1.125rem]" stroke-width="2" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
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
defineProps({
  placeholder: { type: String, default: '' },
  modePill: { type: Object, default: null },
})
const emit = defineEmits(['submit', 'file-selected', 'clear-mode'])

const input = ref('')
const area = ref(null)
const fileInputEl = ref(null)
const plusMenuOpen = ref(false)
const plusRootRef = ref(null)
const isDragging = ref(false)

const ACCEPTED_EXTS = new Set([
  '.pdf', '.docx', '.txt', '.md',
  '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif',
  '.csv', '.xls', '.xlsx',
])

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  if (!ACCEPTED_EXTS.has(ext)) return
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
  emit('file-selected', file)
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

onUnmounted(() => document.removeEventListener('click', onDocumentClick))

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
  if (!msg) return
  emit('submit', { message: msg })
  input.value = ''
  nextTick(autoGrow)
}

defineExpose({
  focus: () => area.value?.focus(),
})
</script>
