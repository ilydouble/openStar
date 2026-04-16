<template>
  <div class="h-screen flex flex-col bg-cream">
    <AppNavbar />
    <!-- 顶栏：返回按钮 -->
    <div class="pt-12 flex items-center gap-3 px-4 py-2.5 border-b border-black/8 bg-cream">
      <button
        @click="router.push('/')"
        class="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition group"
      >
        <svg class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" d="M15 19l-7-7 7-7"/>
        </svg>
        返回首页
      </button>
    </div>
    <div class="flex-1 overflow-hidden">
      <ChatPanel :session-id="sessionId" />
    </div>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { newSessionId } from '../api/agent.js'
import AppNavbar from '../components/AppNavbar.vue'
import ChatPanel from '../components/ChatPanel.vue'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.sessionId || newSessionId()
</script>
