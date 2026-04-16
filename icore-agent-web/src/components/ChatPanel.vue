<template>
  <div class="flex flex-col h-full">
    <!-- 消息列表 -->
    <div ref="scrollEl" class="flex-1 overflow-y-auto px-4 py-6 space-y-6">
      <div v-for="msg in messages" :key="msg.id" :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
        <!-- 用户气泡 -->
        <div v-if="msg.role === 'user'"
          class="max-w-[70%] bg-gray-800 text-white text-sm rounded-2xl rounded-tr-sm px-4 py-3 leading-relaxed">
          {{ msg.content }}
        </div>
        <!-- Agent 气泡 -->
        <div v-else class="max-w-[80%] flex gap-3">
          <div class="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5">A</div>
          <div class="bg-white border border-black/8 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-800 leading-relaxed prose-chat shadow-sm"
            :class="{ 'typing-cursor': msg.streaming }"
            v-html="renderMarkdown(msg.content)"
          />
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading && !streamingMsg" class="flex justify-start gap-3">
        <div class="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center shrink-0">
          <span class="text-white text-xs font-bold">A</span>
        </div>
        <div class="bg-white border border-black/8 rounded-2xl px-4 py-3 flex gap-1 items-center shadow-sm">
          <span v-for="i in 3" :key="i" class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
            :style="{ animationDelay: `${(i-1)*0.15}s` }" />
        </div>
      </div>
    </div>

    <!-- 底部输入框 -->
    <div class="border-t border-black/8 bg-cream px-4 py-3">
      <div class="max-w-3xl mx-auto bg-white rounded-xl border border-black/8 flex items-end gap-2 px-4 py-3 shadow-sm">
        <textarea
          v-model="draft"
          rows="1"
          :placeholder="t('chat.placeholder')"
          class="flex-1 resize-none outline-none text-sm text-gray-800 placeholder-gray-400 bg-transparent max-h-32 leading-relaxed"
          @keydown.enter.exact.prevent="send"
          @input="autoResize"
          ref="textareaEl"
        />
        <button
          @click="send"
          :disabled="loading || !draft.trim()"
          class="w-8 h-8 rounded-lg bg-gray-800 disabled:bg-gray-200 flex items-center justify-center transition shrink-0"
        >
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import { chatStream, newSessionId } from '../api/agent.js'

const { t, locale } = useI18n()

// marked 配置：换行符转 <br>，代码块保留原始文本
marked.setOptions({ breaks: true, gfm: true })

function renderMarkdown(text) {
  if (!text) return '&nbsp;'
  return marked.parse(text)
}

const props = defineProps({ sessionId: String, initialMessage: String })

const messages = ref([])
const draft = ref('')
const loading = ref(false)
const streamingMsg = ref(null)
const scrollEl = ref(null)
const textareaEl = ref(null)
const sessionId = ref(props.sessionId || newSessionId())

// 首条消息自动发送
if (props.initialMessage) {
  sendMessage(props.initialMessage)
}

async function send() {
  const msg = draft.value.trim()
  if (!msg || loading.value) return
  draft.value = ''
  await sendMessage(msg)
}

async function sendMessage(msg) {
  messages.value.push({ id: Date.now(), role: 'user', content: msg })
  loading.value = true
  await scrollBottom()

  const reply = { id: Date.now() + 1, role: 'assistant', content: '', streaming: true }
  streamingMsg.value = reply
  messages.value.push(reply)

  try {
    for await (const token of chatStream(msg, sessionId.value)) {
      reply.content += token
      await scrollBottom()
    }
  } catch (e) {
    reply.content = locale.value === 'zh-CN' ? `⚠️ 请求失败：${e.message}` : `⚠️ Request failed: ${e.message}`
  } finally {
    reply.streaming = false
    streamingMsg.value = null
    loading.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

function autoResize(e) {
  e.target.style.height = 'auto'
  e.target.style.height = e.target.scrollHeight + 'px'
}
</script>
