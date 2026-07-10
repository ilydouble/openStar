<template>
  <div
    class="flex h-dvh min-h-0 overflow-x-hidden bg-zinc-100 text-zinc-950 antialiased transition-colors duration-300 ease-out dark:bg-zinc-950 dark:text-zinc-100"
  >
    <OnboardingModal :show="showOnboarding" @select-scenario="handleOnboardingScenario" @close="showOnboarding = false" />
    <QuotaExceededModal :show="showQuotaModal" :current-plan="quotaExceededPlan" @dismiss="showQuotaModal = false" />

    <!-- 移动端侧边栏遮罩层 -->
    <div
      v-show="sidebarMobileOpen"
      class="fixed inset-0 z-30 bg-zinc-950/35 backdrop-blur-[1px] transition-opacity lg:hidden"
      aria-hidden="true"
      @click="sidebarMobileOpen = false"
    />

    <HomeSidebar
      class="fixed inset-y-0 left-0 z-40 max-lg:shadow-[4px_0_24px_-4px_rgba(0,0,0,0.25)] transition-transform duration-300 ease-out lg:relative lg:z-auto lg:translate-x-0 lg:shadow-none lg:transition-none dark:max-lg:shadow-black/50"
      :class="sidebarMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'"
      :current-session-id="sessionId"
      :recent-sessions="recentSessions"
      :recent-projects="recentProjects"
      :search-results="sessionSearchResults"
      :search-loading="sessionSearchLoading"
      @new="onSidebarNew"
      @navigate="sidebarMobileOpen = false"
      @search="onSessionSearch"
      @delete-session="onDeleteSession"
    />

    <div class="relative flex min-h-0 min-w-0 flex-1 flex-col lg:min-w-0">
      <div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div
          class="absolute inset-0 bg-zinc-100 transition-colors duration-300 ease-out dark:bg-zinc-950"
        />
        <div
          class="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(120,119,198,0.14),transparent)] opacity-60 transition-opacity duration-300 dark:bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(120,119,198,0.18),transparent)] dark:opacity-[0.38]"
        />
        <div
          class="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_100%_50%,rgba(59,130,246,0.06),transparent)] opacity-80 transition-opacity duration-300 dark:bg-[radial-gradient(ellipse_60%_40%_at_100%_50%,rgba(59,130,246,0.08),transparent)] dark:opacity-[0.42]"
        />
      </div>

      <header
        class="relative z-10 flex w-full min-w-0 shrink-0 items-center gap-x-2 gap-y-2 px-3 py-3 sm:px-8 sm:py-4"
      >
        <div class="flex min-w-0 flex-1 items-center gap-2 md:gap-3">
          <button
            type="button"
            class="-ml-0.5 flex min-h-[2.75rem] min-w-[2.75rem] shrink-0 items-center justify-center rounded-xl text-zinc-600 transition-colors hover:bg-zinc-200/80 hover:text-zinc-950 lg:hidden dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
            :aria-label="t('home.sidebar.openMenu')"
            @click="sidebarMobileOpen = true"
          >
            <svg class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div class="hidden min-w-0 flex-wrap items-center gap-2 md:flex">
            <div
              class="rounded-full border border-zinc-200/80 bg-white/85 px-3 py-1.5 text-xs text-zinc-600 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300"
            >
              <span class="font-semibold text-zinc-900 dark:text-white">
                {{ t('home.quota.planPrefix') }}
              </span>
              {{ planSummary?.label || '...' }}
            </div>
            <div
              v-for="item in quotaItems"
              :key="item.label"
              class="rounded-full border border-zinc-200/80 bg-white/85 px-3 py-1.5 text-xs text-zinc-600 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300"
            >
              <span class="font-semibold text-zinc-900 dark:text-white">{{ item.label }}</span>
              {{ item.value }}
            </div>
          </div>

          <div
            class="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto pb-0.5 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden md:hidden"
          >
            <div
              class="shrink-0 rounded-full border border-zinc-200/80 bg-white/85 px-2.5 py-1 text-[11px] text-zinc-600 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300"
            >
              <span class="font-semibold text-zinc-900 dark:text-white">
                {{ t('home.quota.planPrefix') }}
              </span>
              {{ planSummary?.label || '…' }}
            </div>
            <div
              v-for="item in quotaItems"
              :key="'m-' + item.label"
              class="shrink-0 whitespace-nowrap rounded-full border border-zinc-200/80 bg-white/85 px-2.5 py-1 text-[11px] text-zinc-600 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300"
            >
              <span class="font-semibold text-zinc-900 dark:text-white">{{ item.label }}</span>
              {{ item.value }}
            </div>
          </div>
        </div>

        <div class="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <button
            type="button"
            @click="goAccount"
            class="inline-flex min-h-[2.75rem] max-w-[10.5rem] min-w-0 items-center justify-center truncate rounded-full px-3 py-2 text-xs font-medium text-zinc-700 transition-colors duration-300 hover:bg-zinc-200/80 hover:text-zinc-950 sm:max-w-none sm:px-4 sm:text-sm dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
          >
            {{ t('home.accountCenter') }}
          </button>
          <button
            type="button"
            @click="handleSignOut"
            class="inline-flex min-h-[2.75rem] shrink-0 items-center justify-center whitespace-nowrap rounded-full bg-zinc-950 px-3 py-2 text-xs font-semibold text-white shadow-lg shadow-zinc-900/20 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] sm:px-4 sm:text-sm dark:bg-white dark:text-zinc-950 dark:shadow-black/30"
          >
            {{ t('home.signOut') }}
          </button>
        </div>
      </header>

      <main class="relative z-10 flex min-h-0 flex-1 flex-col">
        <div class="flex min-h-0 flex-1 flex-col">
          <div
            v-if="isChatRoute && chatHasTimeline"
            ref="scrollEl"
            class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-6 sm:px-6"
          >
            <ChatTimeline
              :timeline="timeline"
              :attachments="attachmentList"
              :loading="loading"
              :dark="dark"
              :template-labels="templateLabelById"
              @open-document="openDocumentAttachment"
            />
          </div>

          <div
            v-else-if="isChatRoute && !chatHasTimeline"
            class="flex min-h-0 flex-1 flex-col items-center justify-center px-6 pb-6 pt-10"
          >
            <p class="max-w-sm text-center text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
              {{ t('home.chatEmptyHint') }}
            </p>
          </div>

          <div
            v-else-if="isHomeRoute"
            class="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto overflow-x-hidden px-4 py-8 sm:px-10"
          >
            <div class="flex w-full max-w-5xl flex-col items-center text-center">
              <div class="flex flex-col items-center gap-4 animate-home-hero-in">
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400"
                >
                  {{ t('navbar.title') }}
                </p>
                <h1
                  class="text-[1.65rem] font-semibold tracking-[-0.03em] text-zinc-950 sm:text-4xl md:text-[2.5rem] md:leading-[1.15] dark:text-white"
                >
                  {{ t('home.heroTitle') }}
                </h1>
                <p
                  class="max-w-2xl text-sm leading-relaxed text-zinc-600 sm:text-base dark:text-zinc-400"
                >
                  {{ t('home.subtitle') }}
                </p>
              </div>

              <div class="mt-6 w-full max-w-3xl">
                <SearchBar
                  ref="searchRefHome"
                  :placeholder="activeShortcut?.placeholder || ''"
                  :mode-pill="activeShortcutPill"
                  :mode-menu-items="shortcutItems"
                  :active-mode-id="activeShortcutId"
                  :streaming="loading"
                  :send-blocked="uploading"
                  :incognito="incognitoMode"
                  @submit="handleSubmit"
                  @stop="stopAssistantStream"
                  @file-selected="handleFileSelected"
                  @clear-mode="clearShortcut"
                  @select-mode="setComposerMode"
                  @toggle-incognito="toggleIncognitoMode"
                />

                <!-- 附件列表（首页）：会话中的文档/RAG 等；图片与数据文件仅在气泡内展示 -->
                <div v-if="composerAttachments.length || uploading" class="mt-2 flex flex-wrap gap-2 justify-center">
                  <div
                    v-for="att in composerAttachments"
                    :key="att.file_uuid"
                    class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                           border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
                  >
                    <svg class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                    <span class="max-w-[160px] truncate">{{ att.original_filename || att.filename }}</span>
                    <span :class="att.mode === 'rag'
                      ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                      : att.mode === 'data'
                      ? 'rounded bg-emerald-100 px-1 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                      : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'">
                      {{ att.mode === 'rag' ? t('chat.attachmentRag') : att.mode === 'data' ? t('chat.attachmentData') : t('chat.attachmentInline') }}
                    </span>
                    <button @click="deleteAttachment(att.file_uuid)" class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400">
                      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                  </div>
                  <div v-if="uploading" class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-900/20 dark:text-violet-300">
                    <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                    {{ t('chat.uploading') }}
                  </div>
                </div>
                <div v-else-if="uploading" class="mt-2 flex justify-center">
                  <div class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-900/20 dark:text-violet-300">
                    <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                    {{ t('chat.uploading') }}
                  </div>
                </div>
                <div v-if="uploadError" class="mt-2 mx-auto max-w-lg rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 flex items-center gap-2">
                  {{ uploadError }}
                  <button @click="uploadError = ''" class="ml-auto">✕</button>
                </div>
              </div>

              <div class="mt-7 grid w-full max-w-4xl gap-3 text-left sm:grid-cols-2">
                <div
                  v-for="item in homeShortcutItems"
                  :key="item.id"
                  :class="[
                    'rounded-2xl border bg-white/82 p-4 shadow-sm ring-1 ring-black/5 transition-all duration-200 dark:border-white/10 dark:bg-white/[0.045] dark:ring-white/10',
                    activeShortcutId === item.id
                      ? 'border-zinc-950 bg-white shadow-md ring-2 ring-zinc-950/10 dark:border-white/40 dark:bg-white/[0.09] dark:ring-white/20'
                      : 'border-zinc-200/80',
                  ]"
                >
                  <button
                    type="button"
                    :disabled="loading"
                    :aria-pressed="activeShortcutId === item.id"
                    class="group flex w-full items-start gap-3 rounded-xl text-left outline-none transition focus-visible:ring-2 focus-visible:ring-violet-500/50 disabled:opacity-50"
                    @click="toggleShortcut(item.id)"
                  >
                    <span
                      :class="[
                        'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border text-lg shadow-sm ring-1 transition-colors',
                        item.panel,
                        activeShortcutId === item.id ? 'ring-zinc-950/10 dark:ring-white/20' : 'ring-black/5 dark:ring-white/10',
                      ]"
                    >
                      {{ item.emoji }}
                    </span>
                    <span class="min-w-0 flex-1">
                      <span class="block text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">
                        {{ item.role }}
                      </span>
                      <span class="mt-1 block text-base font-semibold text-zinc-950 dark:text-white">
                        {{ item.label }}
                      </span>
                      <span class="mt-2 block text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                        {{ item.summary }}
                      </span>
                    </span>
                  </button>
                  <div class="mt-4 grid grid-cols-2 gap-2">
                    <button
                      v-for="task in item.taskPreviews"
                      :key="task"
                      type="button"
                      :disabled="loading"
                      class="min-h-10 rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs font-semibold text-zinc-700 transition hover:border-zinc-300 hover:bg-white hover:text-zinc-950 disabled:opacity-50 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300 dark:hover:border-white/20 dark:hover:bg-white/[0.08] dark:hover:text-white"
                      @click="startShortcutTask(item.id, task)"
                    >
                      {{ task }}
                    </button>
                  </div>
                </div>
              </div>

              <div
                v-if="activeScenarioTemplate"
                class="mt-6 w-full max-w-4xl rounded-2xl border border-zinc-200/80 bg-white/80 p-5 text-left shadow-sm dark:border-white/10 dark:bg-white/[0.05]"
              >
                <div class="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
                      {{ t('home.scenario.title') }}
                    </p>
                    <h2 class="mt-3 text-xl font-semibold text-zinc-950 dark:text-white">
                      {{ activeScenarioTemplate.title }}
                    </h2>
                    <p class="mt-2 max-w-2xl text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                      {{ activeScenarioTemplate.description }}
                    </p>
                  </div>
                  <div class="rounded-2xl bg-zinc-100 px-4 py-3 text-xs text-zinc-500 dark:bg-white/[0.06] dark:text-zinc-300">
                    {{ activeScenarioTemplate.label }}
                  </div>
                </div>

                <div class="mt-5">
                  <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
                    {{ t('home.scenario.starters') }}
                  </p>
                  <div class="mt-3 grid gap-2 sm:grid-cols-2">
                    <button
                      v-for="starter in activeScenarioTemplate.starters"
                      :key="starter"
                      type="button"
                      class="rounded-xl border border-zinc-200 bg-white px-3 py-3 text-left text-sm font-medium text-zinc-700 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300 dark:hover:text-white"
                      @click="applyStarter(starter)"
                    >
                      {{ starter }}
                    </button>
                  </div>
                </div>

                <div class="mt-5 rounded-xl bg-zinc-50 p-4 dark:bg-white/[0.04]">
                  <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
                    {{ t('home.scenario.accepted') }}
                  </p>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <span
                      v-for="input in activeScenarioTemplate.accepted"
                      :key="input"
                      class="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs text-zinc-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300"
                    >
                      {{ input }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="mt-6 w-full md:hidden">
                <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
                  {{ t('home.recent.title') }}
                </p>
                <div v-if="recentSessions.length" class="mt-3 space-y-2">
                  <button
                    v-for="item in recentSessions"
                    :key="item.sessionId"
                    type="button"
                    class="w-full rounded-2xl border border-zinc-200/80 bg-white/80 px-4 py-3 text-left shadow-sm dark:border-white/10 dark:bg-white/[0.04]"
                    @click="openRecentSession(item.sessionId)"
                  >
                    <p class="text-sm font-semibold text-zinc-800 dark:text-zinc-100">{{ item.title }}</p>
                    <p class="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{{ item.subtitle }}</p>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="isChatRoute"
            class="relative z-30 shrink-0 border-t border-zinc-200 bg-zinc-100/85 p-4 pb-[max(1rem,env(safe-area-inset-bottom))] backdrop-blur-md transition-all duration-500 ease-in-out dark:border-white/10 dark:bg-zinc-950 dark:backdrop-blur-none sm:px-8"
          >
            <!-- 附件列表（对话模式）：文档/RAG 等；图片与数据文件仅在气泡内展示 -->
            <div v-if="composerAttachments.length || uploading || uploadError" class="mx-auto max-w-3xl mb-2">
              <div v-if="composerAttachments.length || uploading" class="flex flex-wrap gap-2">
                <div
                  v-for="att in composerAttachments"
                  :key="att.file_uuid"
                  class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                         border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
                >
                  <svg class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                  </svg>
                  <span class="max-w-[160px] truncate">{{ att.original_filename || att.filename }}</span>
                  <span :class="att.mode === 'rag'
                    ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                    : att.mode === 'data'
                    ? 'rounded bg-emerald-100 px-1 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'">
                    {{ att.mode === 'rag' ? t('chat.attachmentRag') : att.mode === 'data' ? t('chat.attachmentData') : t('chat.attachmentInline') }}
                  </span>
                  <button @click="deleteAttachment(att.file_uuid)" class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400">
                    <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/></svg>
                  </button>
                </div>
                <div v-if="uploading" class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-900/20 dark:text-violet-300">
                  <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/></svg>
                  {{ t('chat.uploading') }}
                </div>
              </div>
              <div v-if="uploadError" class="mt-1 rounded-lg bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 flex items-center gap-2">
                {{ uploadError }}
                <button @click="uploadError = ''" class="ml-auto">✕</button>
              </div>
            </div>
            <SearchBar
              ref="searchRefChat"
              :placeholder="activeShortcut?.placeholder || ''"
              :mode-pill="activeShortcutPill"
              :mode-menu-items="shortcutItems"
              :active-mode-id="activeShortcutId"
              :streaming="loading"
              :send-blocked="uploading"
              :incognito="incognitoMode"
              @submit="handleSubmit"
              @stop="stopAssistantStream"
              @file-selected="handleFileSelected"
              @clear-mode="clearShortcut"
              @select-mode="setComposerMode"
              @toggle-incognito="toggleIncognitoMode"
            />
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, provide, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { QuotaExceededError, workspaceApplication } from '../../index'
import { isDark as isDarkFn } from '../../../../shared/presentation/theme/theme'
import { accountApplication } from '../../../account'
import type { AccountPlan, AccountProject } from '../../../account'
import { authApplication } from '../../../auth'
import HomeSidebar from '../components/HomeSidebar.vue'
import OnboardingModal from '../components/OnboardingModal.vue'
import QuotaExceededModal from '../components/QuotaExceededModal.vue'
import SearchBar from '../components/SearchBar.vue'
import ChatTimeline from '../components/timeline/ChatTimeline.vue'
import {
  SHORTCUT_HINT,
  useWorkspaceCatalog,
} from '../composables/useWorkspaceCatalog'
import {
  composeScenarioPrompt,
  resolveTemplateBubbleText,
} from '../../application/services/scenarioPrompt'
import {
  applyTurnEvent,
  hydrateSessionTimeline,
  timelineToChatRows,
} from '../models/sessionTimeline'
import type { TimelineItem } from '../../domain/models/timeline'
import type { WorkspaceRecord } from '../../domain/models/workspace'
import type {
  ComposerSubmitPayload,
  ProjectSummary,
  SearchBarExpose,
  SessionListItem,
  WorkspaceAttachment,
} from '../models/viewModels'

const {
  completeOnboarding: setWorkspaceOnboardingComplete,
  createSessionId: newSessionId,
  deleteFile: deleteFileAsset,
  deleteSession: clearSession,
  finalizeSession,
  getFileDownloadUrl,
  isOnboardingComplete: getWorkspaceOnboardingComplete,
  loadSession: getSessionState,
  loadSessions: fetchAllSessions,
  searchSessions,
  streamTurn: chatEventStream,
  uploadFile: uploadFileAsset,
} = workspaceApplication

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()

const isHomeRoute = computed(() => route.name === 'workspace')
const isChatRoute = computed(() => route.name === 'workspace-session')

// 移动端侧边栏开关状态
const sidebarMobileOpen = ref(false)

// Onboarding: 首次访问时弹出场景选择引导
const showOnboarding = ref(false)

// Quota: 控制 Token 超限升级弹窗的显示
const showQuotaModal = ref(false)
const quotaExceededPlan = ref('trial')

onMounted(() => {
  const completed = getWorkspaceOnboardingComplete()
  if (!completed && !route.params.sessionId) {
    // 延迟 500ms 弹出，让用户先看到工作台界面
    setTimeout(() => {
      showOnboarding.value = true
    }, 500)
  }
})

/** Activate the scenario selected from onboarding. */
function handleOnboardingScenario(agentHint: string): void {
  const shortcutId = String(agentHint || '').trim()
  if (shortcutItems.value.some((item) => item.id === shortcutId)) {
    activeShortcutId.value = shortcutId
    searchRefHome.value?.focus?.()
  }
  setWorkspaceOnboardingComplete()
  showOnboarding.value = false
}

/** Open one uploaded document in a new browser tab. */
async function openDocumentAttachment(row: WorkspaceAttachment): Promise<void> {
  const fileUuid = String(row?.file_uuid || '').trim()
  if (!fileUuid) return
  try {
    const payload = await getFileDownloadUrl(fileUuid)
    const url = payload?.download_url
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  } catch (err) {
    console.error('Failed to open document attachment:', err)
  }
}

const sessionId = ref(typeof route.params.sessionId === 'string' ? route.params.sessionId : newSessionId())
const timeline = ref(hydrateSessionTimeline({ session_id: sessionId.value, turns: [], attachments: [] }))
const messages = computed(() =>
  timelineToChatRows(timeline.value, {
    attachments: attachmentList.value,
    templateLabels: templateLabelById.value,
  }),
)
const chatHasTimeline = computed(() =>
  loading.value
  || (timeline.value.turns || []).some((turn) =>
    (turn.items || []).some((item) => item.type !== 'context'),
  ),
)
const loading = ref(false)
/** 中止当前 /chat SSE（用户点击停止） */
const streamAbortController = ref<AbortController | null>(null)
/** 中止当前 SSE 流（停止按钮） */
function stopAssistantStream(): void {
  streamAbortController.value?.abort()
}
/** When true, chat is ephemeral: no history, memory injection, or session finalize. */
const incognitoMode = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
const searchRefHome = ref<SearchBarExpose | null>(null)
const searchRefChat = ref<SearchBarExpose | null>(null)
const dark = ref(typeof document !== 'undefined' && document.documentElement.classList.contains('dark'))

// ── 附件状态 ──────────────────────────────────────────────────────────────
const attachmentList = ref<WorkspaceAttachment[]>([])
const uploading = ref(false)
const uploadError = ref('')
const planSummary = ref<AccountPlan | null>(null)
const {
  activeScenarioTemplate,
  activeShortcut,
  activeShortcutId,
  activeShortcutPill,
  homeShortcutItems,
  quotaItems,
  scenarioTemplates,
  shortcutItems,
  templateLabelById,
} = useWorkspaceCatalog(planSummary)
const QUOTA_STREAM_POLL_MS = 30_000
let quotaPollTimer: ReturnType<typeof setInterval> | undefined
const recentSessions = ref<SessionListItem[]>([])
const sessionSearchResults = ref<SessionListItem[]>([])
const sessionSearchLoading = ref(false)
let sessionSearchRequestId = 0
const projectRecords = ref<AccountProject[]>([])
const recentProjects = computed<ProjectSummary[]>(() => {
  return projectRecords.value.map((project) => ({
    id: project.id,
    title: project.title,
    sessions: project.sessionsCount,
    assets: project.assetsCount,
    updatedAt: project.updatedAt,
  }))
})

/** Reset the canonical timeline for a session without touching composer state. */
function resetTimelineState(nextSessionId = sessionId.value): void {
  timeline.value = hydrateSessionTimeline({
    session_id: nextSessionId,
    turns: [],
    attachments: attachmentList.value,
  })
}

/** Add a local-only failed turn when the request fails before backend events arrive. */
function appendLocalErrorTurn(message: string): void {
  const now = Date.now()
  timeline.value.turns.push({
    turnId: `local-error-${now}`,
    status: 'failed',
    error: { message },
    model: null,
    provider: null,
    usage: null,
    startedAt: null,
    completedAt: null,
    durationMs: null,
    items: [{
      itemId: `local-error-item-${now}`,
      type: 'agent_message',
      status: 'completed',
      payload: {
        id: `local-error-item-${now}`,
        type: 'agent_message',
        status: 'completed',
        text: message,
      },
    }],
  })
}

/** 输入区只展示 RAG 等会话级附件；图片与非图片文件均在 SearchBar 预览或气泡内展示 */
const composerAttachments = computed(() =>
  attachmentList.value.filter((a) => a.mode === 'rag'),
)

async function loadPlanSummary(): Promise<void> {
  try {
    planSummary.value = await accountApplication.loadPlan()
  } catch {
    planSummary.value = null
  }
}

/** Poll plan quota while a chat stream is active so token usage stays current. */
function startQuotaPolling(): void {
  stopQuotaPolling()
  quotaPollTimer = setInterval(() => {
    void loadPlanSummary()
  }, QUOTA_STREAM_POLL_MS)
}

function stopQuotaPolling(): void {
  if (quotaPollTimer !== undefined) {
    clearInterval(quotaPollTimer)
    quotaPollTimer = undefined
  }
}

async function refreshAttachments(): Promise<void> {
  // 文件资产由当前会话前端状态持有，旧 session-scoped attachment API 已移除。
}

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])

function extOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

async function handleFileSelected(file: File): Promise<void> {
  if (loading.value || uploading.value) return
  const ext = extOf(file.name)
  if (!IMAGE_EXTS.has(ext)) return
  uploading.value = true
  uploadError.value = ''
  try {
    const uploaded = await uploadFileAsset(file) as WorkspaceAttachment
    attachmentList.value = [...attachmentList.value, uploaded]
    ensureChatRoute()
    const hint = SHORTCUT_HINT[activeShortcutId.value] || ''
    if (!loading.value) {
      await sendUserMessage(t('chat.imageReplyPrompt'), hint, {
        skipUserBubble: true,
        turnFileUuids: [uploaded.file_uuid],
      })
    }
    await loadSessions()
    await loadPlanSummary()
    await syncCurrentProject()
  } catch (error: unknown) {
    uploadError.value = readErrorMessage(error, t('chat.uploadFailed'))
  } finally {
    uploading.value = false
  }
}

async function deleteAttachment(fileUuid: string): Promise<void> {
  try {
    await deleteFileAsset(fileUuid)
    attachmentList.value = attachmentList.value.filter((item) => item.file_uuid !== fileUuid)
    await loadPlanSummary()
    await loadSessions()
    await syncCurrentProject()
  } catch (error: unknown) {
    uploadError.value = readErrorMessage(error, t('chat.deleteFailed'))
  }
}

function resetConversationState(): void {
  stopAssistantStream()
  const nextSessionId = newSessionId()
  sessionId.value = nextSessionId
  incognitoMode.value = false
  loading.value = false
  attachmentList.value = []
  resetTimelineState(nextSessionId)
  uploadError.value = ''
  activeShortcutId.value = ''
  nextTick(() => {
    searchRefHome.value?.clearPendingImage?.()
    searchRefChat.value?.clearPendingImage?.()
    searchRefHome.value?.clearPendingDataFiles?.()
    searchRefChat.value?.clearPendingDataFiles?.()
    ;(isChatRoute.value ? searchRefChat.value : searchRefHome.value)?.focus?.()
    if (scrollEl.value) scrollEl.value.scrollTop = 0
  })
}

/** Schedule durable memory extraction without blocking navigation. */
function scheduleFinalizeSessionIfNeeded(activeSessionId = sessionId.value): void {
  if (incognitoMode.value) return
  if (!messages.value.length) return
  void finalizeSession(activeSessionId).catch((err) => {
    console.error('Failed to finalize session memory:', err)
  })
}

/** Start a fresh session; optionally enable or disable incognito mode. */
function startFreshSession(
  { incognito = false, navigate = true }: { incognito?: boolean; navigate?: boolean } = {},
): void {
  stopAssistantStream()
  const nextSessionId = newSessionId()
  sessionId.value = nextSessionId
  incognitoMode.value = incognito
  loading.value = false
  attachmentList.value = []
  resetTimelineState(nextSessionId)
  uploadError.value = ''
  activeShortcutId.value = ''
  if (navigate) {
    void router.push({ name: 'workspace-session', params: { sessionId: nextSessionId } })
  }
  nextTick(() => {
    searchRefHome.value?.clearPendingImage?.()
    searchRefChat.value?.clearPendingImage?.()
    searchRefHome.value?.clearPendingDataFiles?.()
    searchRefChat.value?.clearPendingDataFiles?.()
    ;(messages.value.length ? searchRefChat.value : searchRefHome.value)?.focus?.()
    if (scrollEl.value) scrollEl.value.scrollTop = 0
  })
}

/** Toggle incognito mode; enabling starts a fresh ephemeral session immediately. */
function toggleIncognitoMode(): void {
  if (incognitoMode.value) {
    startFreshSession({ incognito: false })
    return
  }
  if (messages.value.length > 0) {
    scheduleFinalizeSessionIfNeeded()
  }
  startFreshSession({ incognito: true })
}

watch(
  () => route.name,
  (name) => {
    if (name === 'workspace') resetConversationState()
  },
)

function ensureChatRoute(): void {
  if (route.name === 'workspace') {
    void router.replace({ name: 'workspace-session', params: { sessionId: sessionId.value } })
  }
}

function syncTheme(): void {
  dark.value = isDarkFn()
}

onMounted(async () => {
  syncTheme()
  window.addEventListener('icore-theme-change', syncTheme)
  await loadSessions()
  void loadPlanSummary()
  void loadProjects()
  await hydrateCurrentSession()
})

onUnmounted(() => {
  window.removeEventListener('icore-theme-change', syncTheme)
  stopQuotaPolling()
})

watch(
  () => route.params.sessionId,
  async (nextSessionId) => {
    const resolved = typeof nextSessionId === 'string' ? nextSessionId : newSessionId()
    if (resolved === sessionId.value) return
    const previousSessionId = sessionId.value
    const hadMessages = messages.value.length > 0
    if (hadMessages) {
      scheduleFinalizeSessionIfNeeded(previousSessionId)
    }
    incognitoMode.value = false
    sessionId.value = resolved
    loading.value = false
    attachmentList.value = []
    resetTimelineState(resolved)
    uploadError.value = ''
    activeShortcutId.value = ''
    await loadPlanSummary()
    await hydrateCurrentSession()
  },
)

watch(
  () => [messages.value.length, loading.value],
  () => {
    if (loading.value) {
      void scrollBottom()
    }
  },
)

async function scrollBottom(): Promise<void> {
  await nextTick()
  if (messages.value.length > 0) {
    await nextTick()
  }
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      applyChatScrollBottom()
      requestAnimationFrame(() => {
        applyChatScrollBottom()
        resolve()
      })
    })
  })
}

/** Scroll the chat container to the latest timeline item. */
function applyChatScrollBottom(): void {
  const el = scrollEl.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

function mapSessionSummary(item: WorkspaceRecord): SessionListItem {
  const count = Number(item.turn_count ?? item.message_count ?? 0)
  return {
    sessionId: item.public_id,
    title: (item.title || '').trim() || t('home.heroTitle'),
    subtitle: t('home.recent.messages', { count }),
    updatedAt: item.updated_at,
    messageCount: count,
  }
}

async function loadSessions(): Promise<void> {
  try {
    const { sessions } = await fetchAllSessions()
    recentSessions.value = sessions.map(mapSessionSummary)
  } catch {
    recentSessions.value = []
  }
}

async function onDeleteSession(deletedSessionId: string): Promise<void> {
  try {
    await clearSession(deletedSessionId)
    recentSessions.value = recentSessions.value.filter(
      (s) => s.sessionId !== deletedSessionId,
    )
    sessionSearchResults.value = sessionSearchResults.value.filter(
      (s) => s.sessionId !== deletedSessionId,
    )
    if (deletedSessionId === sessionId.value) {
      resetConversationState()
      await router.push({ name: 'workspace' })
    }
  } catch (err) {
    console.error('Failed to delete session:', err)
  }
}

function mapSearchResult(item: WorkspaceRecord): SessionListItem {
  return {
    sessionId: item.public_id,
    title: (item.title || '').trim() || t('home.heroTitle'),
    snippet: item.snippet || '',
    updatedAt: item.updated_at,
    rank: item.rank,
  }
}

/** Run sidebar session search against the backend full-text index. */
async function onSessionSearch(query: string): Promise<void> {
  const trimmed = String(query || '').trim()
  if (!trimmed) {
    sessionSearchResults.value = []
    sessionSearchLoading.value = false
    return
  }
  sessionSearchLoading.value = true
  const requestId = ++sessionSearchRequestId
  try {
    const payload = await searchSessions(trimmed)
    if (requestId !== sessionSearchRequestId) return
    sessionSearchResults.value = (payload.sessions || []).map(mapSearchResult)
  } catch {
    if (requestId !== sessionSearchRequestId) return
    sessionSearchResults.value = []
  } finally {
    if (requestId === sessionSearchRequestId) {
      sessionSearchLoading.value = false
    }
  }
}

async function loadProjects(): Promise<void> {
  try {
    const payload = await accountApplication.loadProjects()
    projectRecords.value = payload.projects || []
  } catch {
    projectRecords.value = []
  }
}

interface ProjectSyncMeta {
  projectId?: string
  projectTitle?: string
  scenarioId?: string
  sessionTitle?: string
  sessionSubtitle?: string
  title?: string
  subtitle?: string
  attachmentCount?: number
}

async function syncCurrentProject(meta: ProjectSyncMeta = {}): Promise<void> {
  const template = activeScenarioTemplate.value
  const projectId = meta.projectId || template?.id || 'general'
  const projectTitle = meta.projectTitle || template?.title || t('home.heroTitle')
  const sessionTitle = meta.sessionTitle || meta.title || template?.title || t('home.heroTitle')
  const sessionSubtitle = meta.sessionSubtitle || meta.subtitle || template?.description || t('home.subtitle')
  try {
    await accountApplication.syncProject({
      projectId,
      projectTitle,
      scenarioId: template?.id || meta.scenarioId || '',
      sessionId: sessionId.value,
      sessionTitle,
      sessionSubtitle,
      attachmentCount: Number(meta.attachmentCount ?? attachmentList.value.length ?? 0),
    })
    await loadProjects()
  } catch {
    // Keep local continuity even if remote sync fails.
  }
}

async function hydrateCurrentSession(): Promise<void> {
  const hasExplicitSession = typeof route.params.sessionId === 'string'
  if (!hasExplicitSession) {
    await refreshAttachments()
    return
  }
  try {
    const state = await getSessionState(sessionId.value)
    attachmentList.value = Array.isArray(state.attachments)
      ? state.attachments as WorkspaceAttachment[]
      : []
    timeline.value = hydrateSessionTimeline(state)
    await loadSessions()
    const sessionEntry = recentSessions.value.find((item) => item.sessionId === sessionId.value)
    if (!activeShortcutId.value) {
      const matched = scenarioTemplates.value.find((item) => item.title === sessionEntry?.title)
      activeShortcutId.value = matched?.id || ''
    }
    await syncCurrentProject({
      title: sessionEntry?.title || t('home.heroTitle'),
      subtitle: state.summary || sessionEntry?.subtitle || t('home.subtitle'),
      attachmentCount: (state.attachments || []).length,
    })
    if (messages.value.length > 0) {
      await scrollBottom()
    }
  } catch {
    await refreshAttachments()
  }
}

function buildTemplateSendPayload(userQuery: string) {
  const query = String(userQuery || '').trim()
  const template = activeScenarioTemplate.value
  if (!template) {
    return {
      bubbleText: query,
      agentMessage: query,
      templateId: '',
    }
  }
  return {
    bubbleText: resolveTemplateBubbleText(activeShortcut.value?.label || '', query),
    agentMessage: composeScenarioPrompt(query, template),
    templateId: activeShortcutId.value || template.id || '',
  }
}

interface SendUserMessageOptions {
  skipUserBubble?: boolean
  displayCaption?: string
  turnFileUuids?: string[] | null
}

async function sendUserMessage(
  msg: string,
  agentHint = '',
  {
    skipUserBubble = false,
    displayCaption = '',
    turnFileUuids = null,
  }: SendUserMessageOptions = {},
): Promise<void> {
  const text = String(msg ?? '').trim()
  if (!text || loading.value) return
  const { bubbleText, agentMessage, templateId } = buildTemplateSendPayload(text)
  const captionForApi = String(displayCaption || '').trim()
  const fileUuids = Array.isArray(turnFileUuids)
      ? turnFileUuids.map((item: string) => item.trim()).filter(Boolean)
    : []

  void skipUserBubble
  ensureChatRoute()
  loading.value = true
  startQuotaPolling()
  await scrollBottom()

  const ac = new AbortController()
  streamAbortController.value = ac

  try {
    for await (const evt of chatEventStream(bubbleText, sessionId.value, agentHint, {
      signal: ac.signal,
      fileUuids,
      agentMessage: agentMessage !== bubbleText ? agentMessage : '',
      templateId,
      ...(captionForApi ? { displayCaption: captionForApi } : {}),
      incognito: incognitoMode.value,
    })) {
      if (!evt) continue
      applyTurnEvent(timeline.value, evt)
      await scrollBottom()
    }
  } catch (error: unknown) {
    const aborted = error instanceof Error && error.name === 'AbortError'
    if (!aborted) {
      if (error instanceof QuotaExceededError) {
        // 超出 Token 配额 → 显示升级弹窗，而不是报错
        quotaExceededPlan.value = error.currentPlan
        showQuotaModal.value = true
      } else {
        const errorMsg = readErrorMessage(error, '')
        if (errorMsg.includes('401')) {
          authApplication.signOut()
          void router.push({ name: 'auth' })
        } else {
          appendLocalErrorTurn(t('chat.requestFailed', { msg: errorMsg }))
        }
      }
    }
  } finally {
    stopQuotaPolling()
    streamAbortController.value = null
    loading.value = false
    await loadPlanSummary()
    await loadSessions()
    await syncCurrentProject({
      title: activeScenarioTemplate.value?.title || text.slice(0, 36),
      subtitle: text.slice(0, 80),
      sessionTitle: activeScenarioTemplate.value?.title || text.slice(0, 36),
      sessionSubtitle: text.slice(0, 80),
    })
    await scrollBottom()
  }
}

async function handleSubmit({
  message,
  imageFiles,
  dataFiles,
}: ComposerSubmitPayload): Promise<void> {
  if (loading.value || uploading.value) return
  const hint = SHORTCUT_HINT[activeShortcutId.value] || ''
  const text = (message || '').trim()
  const imgs = imageFiles.filter((file) => file.size)
  const datas = dataFiles.filter((file) => file.size)

  if (!imgs.length && !datas.length) {
    if (text) await sendUserMessage(text, hint)
    return
  }

  uploadError.value = ''
  uploading.value = true
  try {
    const uploadedImages: Array<{ file_uuid: string; content: string; filename: string }> = []
    for (const imageFile of imgs) {
      const uploaded = await uploadFileAsset(imageFile) as WorkspaceAttachment
      attachmentList.value = [...attachmentList.value, uploaded]
      const url = uploaded.download_url || URL.createObjectURL(imageFile)
      if (url) {
        uploadedImages.push({
          file_uuid: uploaded.file_uuid,
          content: url,
          filename: uploaded.original_filename || imageFile.name,
        })
      }
    }
    const uploadedDataMeta: Array<{ file_uuid: string; filename: string }> = []
    for (const df of datas) {
      const meta = await uploadFileAsset(df) as WorkspaceAttachment
      attachmentList.value = [...attachmentList.value, meta]
      uploadedDataMeta.push({
        file_uuid: meta.file_uuid,
        filename: meta.original_filename || df.name,
      })
    }
    await loadPlanSummary()

    const hasImages = uploadedImages.length > 0
    const hasData = uploadedDataMeta.length > 0
    if (!hasImages && !hasData) return

    ensureChatRoute()

    let apiText = text
    if (!apiText) {
      if (hasImages && hasData) apiText = t('chat.attachmentsReplyPrompt')
      else if (hasImages) {
        apiText =
          uploadedImages.length > 1 ? t('chat.imageReplyPromptMulti') : t('chat.imageReplyPrompt')
      } else {
        apiText =
          uploadedDataMeta.length > 1 ? t('chat.dataReplyPromptMulti') : t('chat.dataReplyPrompt')
      }
    }
    const turnFileUuids = [
      ...uploadedImages.map((item) => item.file_uuid),
      ...uploadedDataMeta.map((item) => item.file_uuid),
    ].filter(Boolean)
    await sendUserMessage(apiText, hint, {
      skipUserBubble: true,
      turnFileUuids,
      ...(text ? { displayCaption: text } : {}),
    })
  } catch (error: unknown) {
    uploadError.value = readErrorMessage(error, t('chat.uploadFailed'))
  } finally {
    uploading.value = false
    nextTick(() => {
      searchRefHome.value?.clearPendingImage?.()
      searchRefChat.value?.clearPendingImage?.()
      searchRefHome.value?.clearPendingDataFiles?.()
      searchRefChat.value?.clearPendingDataFiles?.()
    })
  }
}

function toggleShortcut(id: string): void {
  activeShortcutId.value = activeShortcutId.value === id ? '' : id
  nextTick(() => {
    ;(isChatRoute.value ? searchRefChat.value : searchRefHome.value)?.focus?.()
  })
}

function setComposerMode(id: string): void {
  activeShortcutId.value = id
  nextTick(() => {
    ;(isChatRoute.value ? searchRefChat.value : searchRefHome.value)?.focus?.()
  })
}

function clearShortcut(): void {
  activeShortcutId.value = ''
}

function applyStarter(starter: string): void {
  const hint = SHORTCUT_HINT[activeShortcutId.value] || ''
  void sendUserMessage(starter, hint)
}

function startShortcutTask(id: string, task: string): void {
  activeShortcutId.value = id
  const hint = SHORTCUT_HINT[id] || ''
  void sendUserMessage(task, hint)
}

function openRecentSession(targetSessionId: string): void {
  void router.push({ name: 'workspace-session', params: { sessionId: targetSessionId } })
}

function onSidebarNew(): void {
  if (!incognitoMode.value) {
    scheduleFinalizeSessionIfNeeded()
  }
  startFreshSession({ incognito: false })
  void syncCurrentProject({
    title: activeScenarioTemplate.value?.title || t('home.heroTitle'),
    subtitle: t('home.subtitle'),
  })
}

function goAccount(): void {
  void router.push({ name: 'account' })
}

function handleSignOut(): void {
  authApplication.signOut()
  void router.push({ name: 'auth' })
}

/** Convert an unknown workspace failure into safe user-facing text. */
function readErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}
</script>
