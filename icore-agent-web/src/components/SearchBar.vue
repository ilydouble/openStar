<template>
  <div class="w-full max-w-2xl mx-auto">
    <!-- 主输入框 -->
    <div class="bg-white rounded-2xl shadow-sm border border-black/8 overflow-hidden">
      <!-- 文本区 -->
      <div class="flex items-center px-4 pt-3 pb-1 gap-2">
        <svg class="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" d="m21 21-4.35-4.35"/>
        </svg>
        <input
          v-model="input"
          :placeholder="tab === 'chat' ? (locale === 'zh-CN' ? '问任何问题，创造任何内容…' : 'Ask any question, create any content...') : (locale === 'zh-CN' ? '搜索知识库、文件、Agent…' : 'Search knowledge base, files, Agent...')"
          class="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-transparent"
          @keydown.enter.prevent="handleSubmit"
        />
        <!-- 语音 -->
        <button class="w-7 h-7 rounded-full hover:bg-gray-100 flex items-center justify-center transition">
          <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M12 1a3 3 0 013 3v7a3 3 0 01-6 0V4a3 3 0 013-3z"/>
            <path stroke-linecap="round" d="M19 10a7 7 0 01-14 0M12 19v4M8 23h8"/>
          </svg>
        </button>
        <!-- Chat 按钮 -->
        <button
          @click="handleSubmit"
          class="flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3v-3z"/>
          </svg>
          Chat
        </button>
      </div>

      <!-- 底部工具栏 -->
      <div class="flex items-center justify-between px-4 pb-2.5 pt-1">
        <div class="flex items-center gap-3">
          <!-- 附件 -->
          <button class="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
            </svg>
            {{ locale === 'zh-CN' ? '附件' : 'Attach' }}
          </button>
          <!-- 选择 Agent -->
          <button class="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <circle cx="12" cy="8" r="4"/><path stroke-linecap="round" d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
            {{ locale === 'zh-CN' ? '选择 Agent' : 'Select Agent' }}
          </button>
        </div>
        <!-- Chat / 搜索 切换 -->
        <div class="flex items-center gap-1 text-xs">
          <button
            v-for="t in tabs" :key="t.key"
            @click="tab = t.key"
            :class="tab === t.key
              ? 'text-gray-900 font-medium'
              : 'text-gray-400 hover:text-gray-600'"
            class="transition px-1"
          >{{ t.label }}</button>
        </div>
      </div>
    </div>

    <!-- 快捷提示词 -->
    <div class="flex flex-wrap gap-2 mt-3 justify-center">
      <button
        v-for="p in prompts" :key="p"
        @click="input = p"
        class="text-xs text-gray-600 bg-white border border-black/8 rounded-full px-3 py-1.5 hover:border-gray-400 hover:text-gray-800 transition shadow-sm"
      >
        {{ p }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()
const emit = defineEmits(['submit'])

const input = ref('')
const tab = ref('chat')
const tabs = computed(() => [
  { key: 'chat', label: locale.value === 'zh-CN' ? 'Chat' : 'Chat' },
  { key: 'search', label: locale.value === 'zh-CN' ? '搜索' : 'Search' },
])
const prompts = computed(() => locale.value === 'zh-CN' ? [
  '帮我分析最新的行业趋势',
  '写一段 Python 数据处理脚本',
  '查询知识库中的产品文档',
  '生成一份竞品对比报告',
] : [
  'Help me analyze the latest industry trends',
  'Write a Python data processing script',
  'Search product documentation in knowledge base',
  'Generate a competitive analysis report',
])

function handleSubmit() {
  const msg = input.value.trim()
  if (!msg) return
  emit('submit', { message: msg, mode: tab.value })
  input.value = ''
}
</script>
