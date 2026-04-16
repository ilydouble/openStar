<template>
  <header class="fixed top-0 inset-x-0 z-50 h-12 bg-cream/80 backdrop-blur-sm border-b border-black/5 flex items-center px-5">
    <!-- 左：Logo + 徽章 -->
    <div class="flex items-center gap-2">
      <!-- Logo 图标 -->
      <div class="w-6 h-6 rounded-md bg-gray-800 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 3a1 1 0 110 2 1 1 0 010-2zm-1 4h2v5H9V9z"/>
        </svg>
      </div>
      <span class="font-semibold text-sm text-gray-900 tracking-tight">{{ t('navbar.title') }}</span>
      <span class="text-[11px] font-medium text-gray-500 bg-gray-200/70 rounded px-1.5 py-0.5 leading-none">
        {{ t('common.platform') }}
      </span>
    </div>

    <!-- 右：语言切换 + 通知 + 用户 -->
    <div class="ml-auto flex items-center gap-3">
      <!-- 语言切换 -->
      <button @click="toggleLocale" class="w-8 h-8 rounded-full hover:bg-black/5 flex items-center justify-center transition" :title="currentLocale === 'zh-CN' ? 'Switch to English' : '切换中文'">
        <span class="text-sm font-medium text-gray-600">{{ currentLocale === 'zh-CN' ? 'EN' : '中' }}</span>
      </button>

      <!-- 通知铃 -->
      <button class="relative w-8 h-8 rounded-full hover:bg-black/5 flex items-center justify-center transition">
        <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
        </svg>
        <span class="absolute top-1 right-1 w-1.5 h-1.5 bg-red-400 rounded-full"></span>
      </button>

      <!-- 用户头像 -->
      <button class="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center text-white text-xs font-semibold hover:opacity-90 transition">
        {{ initials }}
      </button>
      <span class="text-sm text-gray-700 hidden sm:block">{{ t('navbar.admin') }}</span>
    </div>
  </header>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

const { t, locale } = useI18n()

const currentLocale = computed(() => locale.value)

const username = computed(() => t('navbar.admin'))
const initials = computed(() => username.value.charAt(0))

function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  localStorage.setItem('locale', locale.value)
}
</script>
