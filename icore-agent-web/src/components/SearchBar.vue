<template>
  <div class="relative z-0 mx-auto w-full max-w-3xl">
    <div
      class="relative z-0 rounded-2xl border border-zinc-200/80 bg-white/90 p-3 shadow-sm backdrop-blur-md
             transition-all duration-200
             hover:shadow-md
             focus-within:border-zinc-300/90 focus-within:shadow-md
             dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl
             dark:focus-within:border-white/20"
    >
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
                  @click="closePlusMenu"
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
            :placeholder="t('home.inputPlaceholder')"
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
const emit = defineEmits(['submit'])

const input = ref('')
const area = ref(null)
const plusMenuOpen = ref(false)
const plusRootRef = ref(null)

const plusMenuItems = [
  { icon: User, labelKey: 'home.chatInput.selectAgent' },
  { icon: Paperclip, labelKey: 'home.chatInput.addFileOrPhoto' },
  { icon: Image, labelKey: 'home.chatInput.createImage' },
  { icon: Brain, labelKey: 'home.chatInput.thinkDeeply' },
  { icon: Search, labelKey: 'home.chatInput.searchInternet' },
]

function closePlusMenu() {
  plusMenuOpen.value = false
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
