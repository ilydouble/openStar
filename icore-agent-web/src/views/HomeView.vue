<template>
  <div class="min-h-screen bg-cream">
    <AppNavbar />

    <!-- 主体内容，顶部留出 navbar 高度 -->
    <main class="pt-12">
      <div class="max-w-4xl mx-auto px-6 py-16">

        <!-- ① Hero 标题 -->
        <div class="text-center mb-10">
          <h1 class="text-3xl font-semibold text-gray-900 tracking-tight">{{ t('home.title') }}</h1>
          <p class="mt-2 text-sm text-gray-500">{{ t('home.subtitle') }}</p>
        </div>

        <!-- ② 搜索/对话栏 -->
        <SearchBar @submit="handleSearch" />

        <!-- ③ 分隔 -->
        <div class="mt-12 mb-4 flex items-center gap-2">
          <span class="text-[11px] font-semibold tracking-widest text-gray-400 uppercase">核心应用</span>
          <div class="flex-1 h-px bg-black/6"></div>
        </div>

        <!-- ④ Core Applications：3 张大卡片 -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <AgentCard
            v-for="agent in coreAgents"
            :key="agent.id"
            :agent="agent"
            @open="openAgent"
          />
        </div>

        <!-- ⑤ Other Tools -->
        <div class="mt-10 mb-4 flex items-center gap-2">
          <span class="text-[11px] font-semibold tracking-widest text-gray-400 uppercase">工具集</span>
          <div class="flex-1 h-px bg-black/6"></div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <ToolCard
            v-for="tool in otherTools"
            :key="tool.id"
            :tool="tool"
            @open="openTool"
          />
        </div>
      </div>
    </main>

    <!-- ⑥ 全屏 ChatPanel（点击卡片/提交后展开） -->
    <Transition name="slide-up">
      <div v-if="chatVisible" class="fixed inset-0 z-40 flex flex-col bg-cream pt-12">
        <!-- 对话顶栏 -->
        <div class="flex items-center gap-3 px-4 py-2.5 border-b border-black/8 bg-cream">
          <!-- 返回按钮 -->
          <button
            @click="chatVisible = false"
            class="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition group"
          >
            <svg class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" d="M15 19l-7-7 7-7"/>
            </svg>
            {{ locale === 'zh-CN' ? '返回' : 'Back' }}
          </button>
          <!-- 分隔线 -->
          <span class="w-px h-4 bg-black/10"></span>
          <!-- Agent 标题 -->
          <div class="flex items-center gap-2 text-sm font-medium text-gray-700">
            <span>{{ activeAgent?.icon || '🤖' }}</span>
            <span>{{ activeAgent?.name || 'iCore Agent' }}</span>
          </div>
        </div>
        <div class="flex-1 overflow-hidden">
          <ChatPanel :initial-message="pendingMessage" :session-id="sessionId" />
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { newSessionId } from '../api/agent.js'
import AppNavbar from '../components/AppNavbar.vue'
import SearchBar from '../components/SearchBar.vue'
import AgentCard from '../components/AgentCard.vue'
import ToolCard from '../components/ToolCard.vue'
import ChatPanel from '../components/ChatPanel.vue'

const { t, locale } = useI18n()
const router = useRouter()
const chatVisible = ref(false)
const pendingMessage = ref('')
const activeAgent = ref(null)
const sessionId = ref(newSessionId())

// ── 数据：核心 Agent ───────────────────────────────────────
const coreAgents = computed(() => [
  {
    id: 'research', name: t('home.features.research'), category: '信息检索',
    icon: '🔍', iconBg: 'bg-green-500', badge: '精选',
    description: t('home.researchDesc'),
  },
  {
    id: 'code', name: t('home.features.code'), category: '软件开发',
    icon: '⚙️', iconBg: 'bg-amber-500', badge: null,
    description: t('home.codeDesc'),
  },
  {
    id: 'knowledge', name: t('home.features.knowledge'), category: '企业知识库',
    icon: '📚', iconBg: 'bg-blue-500', badge: '新',
    description: t('home.knowledgeDesc'),
  },
])

// ── 数据：工具集 ───────────────────────────────────────────
const otherTools = [
  { id: 'web',  name: '网络搜索', category: '信息检索',  icon: '🌐', iconBg: 'bg-red-400',    description: 'Tavily / DDG 实时网页检索，快速获取最新信息。' },
  { id: 'api',  name: 'API 调用', category: '集成',      icon: '🔌', iconBg: 'bg-purple-500',  description: '向任意 REST API 发送请求，支持 GET/POST 等方法。' },
  { id: 'code', name: '代码执行', category: '计算',      icon: '▶️',  iconBg: 'bg-teal-500',    description: '沙箱内安全运行 Python 代码片段，返回计算结果。' },
  { id: 'file', name: '文件操作', category: '存储',      icon: '📁', iconBg: 'bg-violet-500',  description: '在工作区内读写文件，支持自动目录创建。' },
  { id: 'seq',  name: '序列化任务', category: '自动化',  icon: '⚡', iconBg: 'bg-emerald-500', description: 'mini-SWE 风格逐步 bash 执行，适合多步骤自动化任务。' },
]

// ── 事件处理 ────────────────────────────────────────────────
function handleSearch({ message }) {
  pendingMessage.value = message
  activeAgent.value = null
  sessionId.value = newSessionId()
  chatVisible.value = true
}

function openAgent(agent) {
  activeAgent.value = agent
  pendingMessage.value = locale.value === 'zh-CN'
    ? `你好，我想使用「${agent.name}」，请介绍一下你能做什么？`
    : `Hello, I would like to use "${agent.name}", could you introduce what you can do?`
  sessionId.value = newSessionId()
  chatVisible.value = true
}

function openTool(tool) {
  activeAgent.value = tool
  pendingMessage.value = locale.value === 'zh-CN'
    ? `请演示一下「${tool.name}」工具的用法。`
    : `Please demonstrate how to use the "${tool.name}" tool.`
  sessionId.value = newSessionId()
  chatVisible.value = true
}
</script>

<style scoped>
.slide-up-enter-active, .slide-up-leave-active { transition: transform 0.3s ease, opacity 0.3s ease; }
.slide-up-enter-from, .slide-up-leave-to { transform: translateY(20px); opacity: 0; }
</style>
