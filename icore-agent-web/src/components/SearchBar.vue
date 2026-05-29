<template>
  <div class="relative z-0 mx-auto w-full max-w-3xl">
    <div
      v-if="voiceError"
      role="alert"
      class="mb-2 flex items-start gap-2 rounded-xl border border-red-200/90 bg-red-50 px-3 py-2 text-xs leading-snug text-red-700 shadow-sm dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-200"
    >
      <span class="min-w-0 flex-1">{{ voiceError }}</span>
      <button
        type="button"
        class="shrink-0 rounded-lg px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-red-700 underline-offset-2 hover:underline dark:text-red-300"
        @click="voiceError = ''"
      >
        {{ t('home.voice.dismissError') }}
      </button>
    </div>
    <div
      :class="[
        'relative z-0 rounded-2xl border p-3 shadow-sm backdrop-blur-md transition-all duration-200',
        'hover:shadow-md focus-within:shadow-md',
        incognito
          ? 'border-zinc-400/90 bg-zinc-50/95 ring-2 ring-zinc-400/35 hover:shadow-md focus-within:border-zinc-500/90 focus-within:ring-zinc-400/45 dark:border-zinc-500/55 dark:bg-zinc-900/45 dark:ring-zinc-500/30 dark:focus-within:border-zinc-400/60'
          : 'hover:shadow-md focus-within:border-zinc-300/90',
        !incognito && (isDragging
          ? 'border-violet-400 bg-violet-50/80 shadow-md dark:border-violet-400/60 dark:bg-violet-900/20'
          : 'border-zinc-200/80 bg-white/90 dark:border-white/10 dark:bg-white/5 dark:backdrop-blur-xl dark:focus-within:border-white/20'),
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
      <!-- 无痕模式提示 -->
      <div
        v-if="incognito"
        class="mb-2 flex items-center gap-2 rounded-xl border border-zinc-300/80 bg-zinc-100/90 px-2.5 py-1.5 text-xs font-medium text-zinc-700 dark:border-zinc-500/40 dark:bg-zinc-800/70 dark:text-zinc-200"
        role="status"
      >
        <Lock class="h-3.5 w-3.5 shrink-0 text-zinc-600 dark:text-zinc-300" stroke-width="2" aria-hidden="true" />
        <span class="min-w-0">{{ t('chat.incognito.active') }}</span>
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
      <!-- 待发送非图片文件（Excel / PDF / Word / TXT 等）：与图片一致的「先发预览、发送后进气泡」 -->
      <div v-if="pendingDataFiles.length" class="mb-2 flex flex-col gap-1">
        <div class="flex flex-wrap items-center gap-1.5">
          <div
            v-for="item in pendingDataFiles"
            :key="item.id"
            :title="item.file.name"
            class="relative flex h-14 max-w-[11rem] shrink-0 items-center gap-2 rounded-lg border border-zinc-200/90 bg-zinc-50 px-2.5 shadow-sm ring-1 ring-zinc-200/70 dark:border-white/10 dark:bg-zinc-800/80 dark:ring-white/10"
          >
            <DocumentFileIcon :filename="item.file.name" />
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
              accept=".pdf,.doc,.docx,.txt,.md,.jpg,.jpeg,.png,.webp,.bmp,.gif,.csv,.xls,.xlsx"
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

        <div class="flex min-w-0 flex-1 flex-col px-3">
          <div
            v-if="isRecordingMic"
            class="mb-2 flex flex-col gap-1"
            :aria-label="t('home.voice.recordingVisualizerLabel')"
            role="status"
          >
            <div class="flex h-8 items-end justify-center gap-[3px] rounded-lg bg-red-500/10 px-2 py-1 dark:bg-red-500/15">
              <div
                v-for="(height, index) in meterBars"
                :key="index"
                class="w-[3px] min-h-[4px] max-h-7 shrink-0 rounded-full bg-red-500/90 transition-[height] duration-75 ease-out will-change-[height] dark:bg-red-400"
                :style="{ height: `${height}px` }"
              />
            </div>
            <p class="text-center text-[10px] font-medium uppercase tracking-wider text-red-600/90 dark:text-red-400">
              {{ t('home.voice.recordingActive') }}
            </p>
          </div>

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
            class="relative flex h-9 w-9 items-center justify-center rounded-full border transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/30"
            :class="[
              incognito
                ? 'border-zinc-400/90 bg-zinc-200/90 text-zinc-800 hover:bg-zinc-300/90 dark:border-zinc-500/60 dark:bg-zinc-700/80 dark:text-zinc-100 dark:hover:bg-zinc-600/80'
                : 'border-transparent text-zinc-500 hover:bg-zinc-100/90 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-white/10 dark:hover:text-white',
              (streaming || sendBlocked) ? 'pointer-events-none opacity-35' : '',
            ]"
            :disabled="streaming || sendBlocked"
            :aria-pressed="incognito"
            :aria-label="incognito ? t('chat.incognito.disable') : t('chat.incognito.enable')"
            :title="incognito ? t('chat.incognito.disableHint') : t('chat.incognito.enableHint')"
            @click.stop="$emit('toggle-incognito')"
          >
            <Lock v-if="incognito" class="h-[1.125rem] w-[1.125rem]" stroke-width="2" aria-hidden="true" />
            <LockOpen v-else class="h-[1.125rem] w-[1.125rem]" stroke-width="2" aria-hidden="true" />
          </button>

          <button
            type="button"
            class="relative flex h-9 w-9 items-center justify-center rounded-full border border-transparent text-zinc-500 transition-colors duration-200 hover:bg-zinc-100/90 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/30 dark:text-zinc-400 dark:hover:bg-white/10 dark:hover:text-white"
            :class="[
              isRecordingMic
                ? 'mic-live border-2 border-red-500 bg-red-50 text-red-600 dark:border-red-400 dark:bg-red-950/35 dark:text-red-300'
                : '',
              micDisabled ? 'pointer-events-none opacity-35' : '',
            ]"
            :disabled="micDisabled"
            :aria-busy="isTranscribingVoice"
            :aria-pressed="isRecordingMic"
            :aria-label="isTranscribingVoice ? t('home.voice.transcribingHint') : t('home.voice.micLabel')"
            :title="t('home.voice.hintToggle')"
            @click.stop="onMicToggle"
          >
            <Loader2 v-if="isTranscribingVoice" class="h-[1.125rem] w-[1.125rem] animate-spin" stroke-width="2" />
            <Mic v-else class="h-[1.125rem] w-[1.125rem]" stroke-width="2" />
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
  Loader2,
  SendHorizontal,
  LayoutGrid,
  ChevronLeft,
  Lock,
  LockOpen,
} from 'lucide-vue-next'

import { transcribeSpeech } from '../api/agent.js'
import DocumentFileIcon from './DocumentFileIcon.vue'

const TEXTAREA_MAX_HEIGHT = 200

const { t, locale } = useI18n()

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
  /** 无痕模式：不写入历史、不注入记忆 */
  incognito: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'file-selected', 'clear-mode', 'stop', 'select-mode', 'toggle-incognito'])

const modeMenuItemsList = computed(() =>
  Array.isArray(props.modeMenuItems) ? props.modeMenuItems : [],
)

/** Voice input: idle | recording | transcribing */
const voiceStage = ref('idle')
const voiceError = ref('')
/** @type {import('vue').Ref<AbortController | null>} */
const transcribeAbort = ref(null)
/** @type {import('vue').Ref<MediaStream | null>} */
const micStream = ref(null)
/** @type {import('vue').Ref<MediaRecorder | null>} */
const mediaRecorder = ref(null)
/** @type {import('vue').Ref<Blob[]>} */
const micChunks = ref([])
/** After stop: optionally submit composer once transcription finishes */
const voiceSubmitAfterTranscribe = ref(false)

/** Level meter (px height per bar), driven by AnalyserNode during recording */
const NUM_METER_BARS = 14
const meterBars = ref(Array.from({ length: NUM_METER_BARS }, () => 4))

let audioContext = /** @type {AudioContext | null} */ (null)
let mediaStreamSource = /** @type {MediaStreamAudioSourceNode | null} */ (null)
let analyserNode = /** @type {AnalyserNode | null} */ (null)
let meterRaf = 0

const isRecordingMic = computed(() => voiceStage.value === 'recording')
const isTranscribingVoice = computed(() => voiceStage.value === 'transcribing')

const micDisabled = computed(
  () => props.streaming || props.sendBlocked || isTranscribingVoice.value,
)

function stopMeterLoop() {
  if (meterRaf) cancelAnimationFrame(meterRaf)
  meterRaf = 0
  meterBars.value = Array.from({ length: NUM_METER_BARS }, () => 4)
}

function startMeterLoop() {
  stopMeterLoop()
  const tick = () => {
    if (!analyserNode || voiceStage.value !== 'recording') return
    const n = analyserNode.frequencyBinCount
    const data = new Uint8Array(n)
    analyserNode.getByteFrequencyData(data)
    const binSize = Math.max(1, Math.floor(n / NUM_METER_BARS))
    const next = []
    for (let i = 0; i < NUM_METER_BARS; i++) {
      let sum = 0
      const start = i * binSize
      const end = Math.min(n, start + binSize)
      for (let j = start; j < end; j++) sum += data[j]
      const avg = sum / (end - start) / 255
      const h = Math.round(4 + avg * 26)
      next.push(Math.min(28, Math.max(4, h)))
    }
    meterBars.value = next
    meterRaf = requestAnimationFrame(tick)
  }
  meterRaf = requestAnimationFrame(tick)
}

function teardownAudioGraph() {
  stopMeterLoop()
  try {
    mediaStreamSource?.disconnect()
  } catch {
    /* ignore */
  }
  mediaStreamSource = null
  try {
    analyserNode?.disconnect()
  } catch {
    /* ignore */
  }
  analyserNode = null
  try {
    if (audioContext && audioContext.state !== 'closed')
      void audioContext.close()
  } catch {
    /* ignore */
  }
  audioContext = null
}

function stopMicTracks() {
  micStream.value?.getTracks().forEach((t) => {
    try {
      t.stop()
    } catch {
      /* ignore */
    }
  })
  micStream.value = null
}

function pickRecorderMime() {
  const cands = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
  for (const c of cands) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(c)) return c
  }
  return ''
}

function insertTranscript(text) {
  const raw = String(text || '').trim()
  if (!raw) return
  const el = area.value
  const spacer = input.value && !input.value.endsWith(' ') ? ' ' : ''
  const chunk = spacer + raw
  if (!el) {
    input.value += chunk
    nextTick(autoGrow)
    return
  }
  const start = typeof el.selectionStart === 'number' ? el.selectionStart : input.value.length
  const end = typeof el.selectionEnd === 'number' ? el.selectionEnd : input.value.length
  const v = input.value
  input.value = v.slice(0, start) + chunk + v.slice(end)
  nextTick(() => {
    autoGrow()
    const pos = start + chunk.length
    try {
      el.selectionStart = el.selectionEnd = pos
      el.focus()
    } catch {
      /* ignore */
    }
  })
}

async function runTranscription(blob, filename, submitAfter = false) {
  transcribeAbort.value?.abort()
  const ac = new AbortController()
  transcribeAbort.value = ac
  voiceStage.value = 'transcribing'
  try {
    const text = await transcribeSpeech(blob, {
      language: locale.value,
      signal: ac.signal,
      filename,
    })
    if (text) insertTranscript(text)
    if (submitAfter && !props.streaming && !props.sendBlocked) {
      await nextTick()
      handleSubmit()
    }
  } catch (err) {
    if (err?.name === 'AbortError') return
    const msg = err && typeof err.message === 'string' ? err.message.trim() : ''
    voiceError.value = msg || t('home.voice.transcribeFailed')
  } finally {
    if (transcribeAbort.value === ac) transcribeAbort.value = null
    voiceStage.value = 'idle'
  }
}

function discardActiveRecorderWithoutTranscript() {
  teardownAudioGraph()
  voiceSubmitAfterTranscribe.value = false
  const rec = mediaRecorder.value
  if (rec) {
    rec.onstop = null
    if (rec.state !== 'inactive') {
      try {
        rec.stop()
      } catch {
        /* ignore */
      }
    }
  }
  mediaRecorder.value = null
  micChunks.value = []
  stopMicTracks()
  if (voiceStage.value !== 'transcribing') voiceStage.value = 'idle'
}

function attachRecorderStopForTranscribe(rec) {
  rec.onstop = () => {
    const submitAfter = voiceSubmitAfterTranscribe.value
    voiceSubmitAfterTranscribe.value = false
    teardownAudioGraph()

    const mt = rec.mimeType || 'audio/webm'
    const parts = micChunks.value
    micChunks.value = []
    mediaRecorder.value = null
    stopMicTracks()

    const blob = new Blob(parts, { type: mt })
    if (!blob.size) {
      voiceError.value = t('home.voice.emptyRecording')
      voiceStage.value = 'idle'
      if (submitAfter && !props.streaming && !props.sendBlocked) {
        void nextTick(() => handleSubmit())
      }
      return
    }
    const ext = mt.includes('mp4') ? 'm4a' : 'webm'
    void runTranscription(blob, `speech.${ext}`, submitAfter)
  }
}

async function startVoiceCapture() {
  if (props.streaming || props.sendBlocked || voiceStage.value === 'transcribing') return
  discardActiveRecorderWithoutTranscript()
  voiceError.value = ''
  transcribeAbort.value?.abort()
  transcribeAbort.value = null
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
    voiceError.value = t('home.voice.micUnavailable')
    return
  }
  let stream
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
  } catch (err) {
    voiceError.value =
      err && err.name === 'NotAllowedError'
        ? t('home.voice.permissionDenied')
        : t('home.voice.micUnavailable')
    return
  }
  micStream.value = stream

  teardownAudioGraph()
  try {
    const AC = window.AudioContext || window.webkitAudioContext
    if (AC) {
      audioContext = new AC()
      if (audioContext.state === 'suspended')
        await audioContext.resume()
      mediaStreamSource = audioContext.createMediaStreamSource(stream)
      analyserNode = audioContext.createAnalyser()
      analyserNode.fftSize = 256
      analyserNode.smoothingTimeConstant = 0.62
      mediaStreamSource.connect(analyserNode)
      startMeterLoop()
    }
  } catch {
    /* metering is optional */
  }

  micChunks.value = []
  const mime = pickRecorderMime()
  let rec
  try {
    rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
  } catch {
    rec = new MediaRecorder(stream)
  }
  mediaRecorder.value = rec
  rec.ondataavailable = (e) => {
    if (e.data && e.data.size) micChunks.value.push(e.data)
  }
  attachRecorderStopForTranscribe(rec)
  try {
    rec.start(250)
    voiceStage.value = 'recording'
  } catch {
    discardActiveRecorderWithoutTranscript()
    voiceError.value = t('home.voice.micUnavailable')
  }
}

/** @param {{ submitAfter?: boolean }} [opts] */
function stopVoiceCaptureAndTranscribe(opts = {}) {
  const { submitAfter = false } = opts
  voiceSubmitAfterTranscribe.value = submitAfter
  const rec = mediaRecorder.value
  if (!rec || rec.state === 'inactive') {
    const wantsSubmit = submitAfter
    discardActiveRecorderWithoutTranscript()
    if (wantsSubmit && !props.streaming && !props.sendBlocked) void nextTick(() => handleSubmit())
    return
  }
  try {
    rec.stop()
  } catch {
    voiceSubmitAfterTranscribe.value = false
    discardActiveRecorderWithoutTranscript()
  }
}

function onMicToggle() {
  if (micDisabled.value && voiceStage.value === 'idle') return
  if (isTranscribingVoice.value) return
  if (isRecordingMic.value) {
    stopVoiceCaptureAndTranscribe({ submitAfter: false })
    return
  }
  void startVoiceCapture()
}

function disposeVoiceUi() {
  transcribeAbort.value?.abort()
  transcribeAbort.value = null
  discardActiveRecorderWithoutTranscript()
}
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

const hasComposerPayload = computed(
  () =>
    !!input.value.trim()
    || pendingImages.value.length > 0
    || pendingDataFiles.value.length > 0,
)

/** 流式输出时可点停止；录音中可点发送以结束录音并转写后发送；转写中禁用 */
const mainActionDisabled = computed(() => {
  if (props.streaming) return false
  if (props.sendBlocked) return true
  if (isTranscribingVoice.value) return true
  if (isRecordingMic.value) return false
  return !hasComposerPayload.value
})

function onMainAction() {
  if (props.streaming) {
    emit('stop')
    return
  }
  if (isRecordingMic.value) {
    stopVoiceCaptureAndTranscribe({ submitAfter: true })
    return
  }
  handleSubmit()
}

function onEnterInTextarea() {
  if (props.streaming) return
  if (isRecordingMic.value) {
    stopVoiceCaptureAndTranscribe({ submitAfter: true })
    return
  }
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
  '.pdf', '.doc', '.docx', '.txt', '.md',
  '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif',
  '.csv', '.xls', '.xlsx',
])

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])
/** 所有非图片的可上传扩展名（与 Excel 共用同一 pending 流程） */
const DOCUMENT_EXTS = new Set([
  '.pdf', '.doc', '.docx', '.txt', '.md',
  '.csv', '.xls', '.xlsx',
])

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

/** 将非图片文件加入待发送列表（总数不超过 MAX_PENDING_DATA_FILES） */
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
    if (!DOCUMENT_EXTS.has(ext)) continue
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
  const allDocuments = files.length > 0 && files.every((f) => DOCUMENT_EXTS.has(extOf(f.name)))
  if (allDocuments) {
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
  if (DOCUMENT_EXTS.has(ext)) {
    addPendingDataFiles([file])
  }
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
    const allDocuments = files.length > 0 && files.every((f) => DOCUMENT_EXTS.has(extOf(f.name)))
    if (allDocuments) {
      addPendingDataFiles(files)
    } else {
      const file = files[0]
      const ext = extOf(file.name)
      if (IMAGE_EXTS.has(ext)) {
        addPendingImageFiles([file])
      } else if (DOCUMENT_EXTS.has(ext)) {
        addPendingDataFiles([file])
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
  disposeVoiceUi()
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

<style scoped>
@keyframes mic-live-ring {
  0%,
  100% {
    opacity: 1;
    box-shadow:
      0 0 0 2px rgb(239 68 68 / 0.55),
      0 0 12px rgb(239 68 68 / 0.28);
  }
  50% {
    opacity: 0.86;
    box-shadow:
      0 0 0 7px rgb(239 68 68 / 0.22),
      0 0 18px rgb(239 68 68 / 0.42);
  }
}

.mic-live {
  animation: mic-live-ring 1.1s ease-in-out infinite;
}
</style>
