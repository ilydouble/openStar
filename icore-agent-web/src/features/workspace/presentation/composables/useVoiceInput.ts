import { computed, nextTick, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { workspaceApplication } from '../../index'

interface VoiceInputOptions {
  input: Ref<string>
  textarea: Ref<HTMLTextAreaElement | null>
  isStreaming: () => boolean
  isSendBlocked: () => boolean
  onResize: () => void
  onSubmit: () => void
}

const NUM_METER_BARS = 14

/** Manage microphone capture, level metering, and backend transcription. */
export function useVoiceInput(options: VoiceInputOptions) {
  const { t, locale } = useI18n()
  const voiceStage = ref<'idle' | 'recording' | 'transcribing'>('idle')
  const voiceError = ref('')
  const transcribeAbort = ref<AbortController | null>(null)
  const micStream = ref<MediaStream | null>(null)
  const mediaRecorder = ref<MediaRecorder | null>(null)
  const micChunks = ref<Blob[]>([])
  const submitAfterTranscription = ref(false)
  const meterBars = ref(Array.from({ length: NUM_METER_BARS }, () => 4))
  let audioContext: AudioContext | null = null
  let mediaStreamSource: MediaStreamAudioSourceNode | null = null
  let analyserNode: AnalyserNode | null = null
  let meterAnimationFrame = 0

  const isRecordingMic = computed(() => voiceStage.value === 'recording')
  const isTranscribingVoice = computed(() => voiceStage.value === 'transcribing')
  const micDisabled = computed(
    () => options.isStreaming() || options.isSendBlocked() || isTranscribingVoice.value,
  )

  /** Stop the level-meter animation and reset its bars. */
  function stopMeterLoop(): void {
    if (meterAnimationFrame) cancelAnimationFrame(meterAnimationFrame)
    meterAnimationFrame = 0
    meterBars.value = Array.from({ length: NUM_METER_BARS }, () => 4)
  }

  /** Start updating microphone level bars from the Web Audio analyser. */
  function startMeterLoop(): void {
    stopMeterLoop()
    const tick = (): void => {
      if (!analyserNode || voiceStage.value !== 'recording') return
      const size = analyserNode.frequencyBinCount
      const data = new Uint8Array(size)
      analyserNode.getByteFrequencyData(data)
      const binSize = Math.max(1, Math.floor(size / NUM_METER_BARS))
      const next: number[] = []
      for (let index = 0; index < NUM_METER_BARS; index += 1) {
        let sum = 0
        const start = index * binSize
        const end = Math.min(size, start + binSize)
        for (let cursor = start; cursor < end; cursor += 1) sum += data[cursor]
        const average = sum / Math.max(1, end - start) / 255
        next.push(Math.min(28, Math.max(4, Math.round(4 + average * 26))))
      }
      meterBars.value = next
      meterAnimationFrame = requestAnimationFrame(tick)
    }
    meterAnimationFrame = requestAnimationFrame(tick)
  }

  /** Disconnect and close the optional Web Audio metering graph. */
  function teardownAudioGraph(): void {
    stopMeterLoop()
    try {
      mediaStreamSource?.disconnect()
      analyserNode?.disconnect()
      if (audioContext?.state !== 'closed') void audioContext?.close()
    } catch {
      // Metering is optional; cleanup failures should not block transcription.
    }
    mediaStreamSource = null
    analyserNode = null
    audioContext = null
  }

  /** Stop every active microphone track. */
  function stopMicTracks(): void {
    micStream.value?.getTracks().forEach((track) => track.stop())
    micStream.value = null
  }

  /** Select the first browser-supported audio recording MIME type. */
  function recorderMimeType(): string {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
    return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || ''
  }

  /** Insert transcribed text at the current textarea selection. */
  function insertTranscript(text: string): void {
    const transcript = text.trim()
    if (!transcript) return
    const textarea = options.textarea.value
    const spacer = options.input.value && !options.input.value.endsWith(' ') ? ' ' : ''
    const chunk = spacer + transcript
    if (!textarea) {
      options.input.value += chunk
      void nextTick(options.onResize)
      return
    }
    const start = textarea.selectionStart ?? options.input.value.length
    const end = textarea.selectionEnd ?? options.input.value.length
    options.input.value = options.input.value.slice(0, start) + chunk + options.input.value.slice(end)
    void nextTick(() => {
      options.onResize()
      const position = start + chunk.length
      textarea.setSelectionRange(position, position)
      textarea.focus()
    })
  }

  /** Send captured audio to the workspace transcription use case. */
  async function runTranscription(blob: Blob, filename: string, submitAfter = false): Promise<void> {
    transcribeAbort.value?.abort()
    const controller = new AbortController()
    transcribeAbort.value = controller
    voiceStage.value = 'transcribing'
    try {
      const text = await workspaceApplication.transcribeSpeech(blob, {
        language: locale.value,
        signal: controller.signal,
        filename,
      })
      if (text) insertTranscript(text)
      if (submitAfter && !options.isStreaming() && !options.isSendBlocked()) {
        await nextTick()
        options.onSubmit()
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') return
      voiceError.value = error instanceof Error && error.message
        ? error.message
        : t('home.voice.transcribeFailed')
    } finally {
      if (transcribeAbort.value === controller) transcribeAbort.value = null
      voiceStage.value = 'idle'
    }
  }

  /** Stop and discard active recording without transcription. */
  function discardRecorder(): void {
    teardownAudioGraph()
    submitAfterTranscription.value = false
    const recorder = mediaRecorder.value
    if (recorder) {
      recorder.onstop = null
      if (recorder.state !== 'inactive') recorder.stop()
    }
    mediaRecorder.value = null
    micChunks.value = []
    stopMicTracks()
    if (voiceStage.value !== 'transcribing') voiceStage.value = 'idle'
  }

  /** Attach the handler that turns a completed recording into transcription. */
  function attachStopHandler(recorder: MediaRecorder): void {
    recorder.onstop = () => {
      const shouldSubmit = submitAfterTranscription.value
      submitAfterTranscription.value = false
      teardownAudioGraph()
      const mimeType = recorder.mimeType || 'audio/webm'
      const blob = new Blob(micChunks.value, { type: mimeType })
      micChunks.value = []
      mediaRecorder.value = null
      stopMicTracks()
      if (!blob.size) {
        voiceError.value = t('home.voice.emptyRecording')
        voiceStage.value = 'idle'
        if (shouldSubmit && !options.isStreaming() && !options.isSendBlocked()) {
          void nextTick(options.onSubmit)
        }
        return
      }
      const extension = mimeType.includes('mp4') ? 'm4a' : 'webm'
      void runTranscription(blob, `speech.${extension}`, shouldSubmit)
    }
  }

  /** Request microphone access and begin recording. */
  async function startVoiceCapture(): Promise<void> {
    if (options.isStreaming() || options.isSendBlocked() || isTranscribingVoice.value) return
    discardRecorder()
    voiceError.value = ''
    transcribeAbort.value?.abort()
    if (!navigator.mediaDevices?.getUserMedia) {
      voiceError.value = t('home.voice.micUnavailable')
      return
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      })
    } catch (error: unknown) {
      voiceError.value = error instanceof Error && error.name === 'NotAllowedError'
        ? t('home.voice.permissionDenied')
        : t('home.voice.micUnavailable')
      return
    }
    micStream.value = stream
    try {
      const webkitWindow = window as typeof window & { webkitAudioContext?: typeof AudioContext }
      const AudioContextConstructor = window.AudioContext || webkitWindow.webkitAudioContext
      if (AudioContextConstructor) {
        audioContext = new AudioContextConstructor()
        if (audioContext.state === 'suspended') await audioContext.resume()
        mediaStreamSource = audioContext.createMediaStreamSource(stream)
        analyserNode = audioContext.createAnalyser()
        analyserNode.fftSize = 256
        analyserNode.smoothingTimeConstant = 0.62
        mediaStreamSource.connect(analyserNode)
        startMeterLoop()
      }
    } catch {
      // Recording remains available if visual metering cannot start.
    }
    const mimeType = recorderMimeType()
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream)
    mediaRecorder.value = recorder
    recorder.ondataavailable = (event) => {
      if (event.data.size) micChunks.value.push(event.data)
    }
    attachStopHandler(recorder)
    try {
      recorder.start(250)
      voiceStage.value = 'recording'
    } catch {
      discardRecorder()
      voiceError.value = t('home.voice.micUnavailable')
    }
  }

  /** Stop recording and optionally submit after transcription. */
  function stopVoiceCapture({ submitAfter = false }: { submitAfter?: boolean } = {}): void {
    submitAfterTranscription.value = submitAfter
    const recorder = mediaRecorder.value
    if (!recorder || recorder.state === 'inactive') {
      discardRecorder()
      if (submitAfter && !options.isStreaming() && !options.isSendBlocked()) {
        void nextTick(options.onSubmit)
      }
      return
    }
    try {
      recorder.stop()
    } catch {
      submitAfterTranscription.value = false
      discardRecorder()
    }
  }

  /** Toggle microphone recording from the composer button. */
  function onMicToggle(): void {
    if (micDisabled.value && voiceStage.value === 'idle') return
    if (isTranscribingVoice.value) return
    if (isRecordingMic.value) stopVoiceCapture()
    else void startVoiceCapture()
  }

  /** Abort transcription and release every microphone resource. */
  function disposeVoiceInput(): void {
    transcribeAbort.value?.abort()
    transcribeAbort.value = null
    discardRecorder()
  }

  return {
    disposeVoiceInput,
    isRecordingMic,
    isTranscribingVoice,
    meterBars,
    micDisabled,
    onMicToggle,
    stopVoiceCapture,
    voiceError,
  }
}
