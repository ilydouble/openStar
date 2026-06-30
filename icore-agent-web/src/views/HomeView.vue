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
            class="flex min-h-0 flex-1 flex-col items-center justify-[safe_center] overflow-y-auto overflow-x-hidden px-4 py-8 sm:px-10"
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

              <div class="mt-6 w-full max-w-4xl">
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

                <!-- Pi mode: pick / upload the sandboxed project Pi should analyze -->
                <div v-if="activeShortcutId === 'pi'" class="mt-2 flex flex-wrap items-center justify-center gap-2">
                  <button
                    type="button"
                    @click="triggerPiProjectUpload"
                    class="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  >
                    <span aria-hidden="true">📁</span>
                    {{ t('home.pi.uploadProject') }}
                  </button>
                  <div class="relative">
                    <button
                      type="button"
                      @click="togglePiWorkspacePicker"
                      class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                             border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                      <span class="max-w-[180px] truncate">{{ activePiWorkspace?.title || t('home.pi.selectProject') }}</span>
                      <span aria-hidden="true">▾</span>
                    </button>
                    <div
                      v-if="piWorkspacePickerOpen"
                      class="absolute left-0 z-20 mt-1 w-64 max-h-72 overflow-auto rounded-xl border border-zinc-200 bg-white p-1.5 text-xs shadow-lg dark:border-white/10 dark:bg-zinc-900"
                    >
                      <div v-if="piWorkspacesLoading" class="px-2 py-1.5 text-zinc-400">…</div>
                      <div v-else-if="!piWorkspaces.length" class="px-2 py-1.5 text-zinc-400">{{ t('home.pi.noProjects') }}</div>
                      <button
                        v-for="ws in piWorkspaces"
                        :key="ws.id"
                        type="button"
                        @click="selectPiWorkspace(ws)"
                        :class="['flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800',
                                 ws.id === activePiWorkspaceId ? 'bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300' : 'text-zinc-700 dark:text-zinc-300']"
                      >
                        <span class="truncate">{{ ws.title }}</span>
                        <span
                          role="button"
                          aria-label="remove"
                          @click.stop="removePiWorkspace(ws)"
                          class="shrink-0 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:hover:text-red-400"
                        >✕</span>
                      </button>
                      <button
                        v-if="activePiWorkspaceId"
                        type="button"
                        @click="clearActivePiWorkspace"
                        class="mt-0.5 flex w-full items-center rounded-lg px-2 py-1.5 text-left text-zinc-500 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                      >{{ t('home.pi.clearSelection') }}</button>
                    </div>
                  </div>
                  <span v-if="piUploadState && piUploadState.stage !== 'error'" class="text-xs text-zinc-400">
                    {{ t(`home.pi.${piUploadState.stage}`) }}
                  </span>
                  <span v-else-if="piUploadState && piUploadState.stage === 'error'" class="text-xs text-red-500">
                    {{ t('home.pi.uploadError', { msg: piUploadState.error }) }}
                  </span>
                  <span v-if="activePiWorkspace" class="text-[11px] text-zinc-400">{{ t('home.pi.activeHint') }}</span>
                </div>
                <input
                  ref="piProjectInputEl"
                  type="file"
                  webkitdirectory
                  multiple
                  class="hidden"
                  @change="handlePiProjectFolderSelected"
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

              <div class="mt-7 grid w-full max-w-4xl gap-3 text-left sm:grid-cols-2 xl:grid-cols-3">
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
              @composer-resize="handleComposerResize"
            />

            <!-- Pi mode: pick / upload the sandboxed project Pi should analyze -->
            <div v-if="activeShortcutId === 'pi'" class="mt-2 flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                @click="triggerPiProjectUpload"
                class="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                <span aria-hidden="true">📁</span>
                {{ t('home.pi.uploadProject') }}
              </button>
              <div class="relative">
                <button
                  type="button"
                  @click="togglePiWorkspacePicker"
                  class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                         border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  <span class="max-w-[180px] truncate">{{ activePiWorkspace?.title || t('home.pi.selectProject') }}</span>
                  <span aria-hidden="true">▾</span>
                </button>
                <div
                  v-if="piWorkspacePickerOpen"
                  class="absolute left-0 z-20 mt-1 w-64 max-h-72 overflow-auto rounded-xl border border-zinc-200 bg-white p-1.5 text-xs shadow-lg dark:border-white/10 dark:bg-zinc-900"
                >
                  <div v-if="piWorkspacesLoading" class="px-2 py-1.5 text-zinc-400">…</div>
                  <div v-else-if="!piWorkspaces.length" class="px-2 py-1.5 text-zinc-400">{{ t('home.pi.noProjects') }}</div>
                  <button
                    v-for="ws in piWorkspaces"
                    :key="ws.id"
                    type="button"
                    @click="selectPiWorkspace(ws)"
                    :class="['flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800',
                             ws.id === activePiWorkspaceId ? 'bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300' : 'text-zinc-700 dark:text-zinc-300']"
                  >
                    <span class="truncate">{{ ws.title }}</span>
                    <span
                      role="button"
                      aria-label="remove"
                      @click.stop="removePiWorkspace(ws)"
                      class="shrink-0 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:hover:text-red-400"
                    >✕</span>
                  </button>
                  <button
                    v-if="activePiWorkspaceId"
                    type="button"
                    @click="clearActivePiWorkspace"
                    class="mt-0.5 flex w-full items-center rounded-lg px-2 py-1.5 text-left text-zinc-500 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                  >{{ t('home.pi.clearSelection') }}</button>
                </div>
              </div>
              <span v-if="piUploadState && piUploadState.stage !== 'error'" class="text-xs text-zinc-400">
                {{ t(`home.pi.${piUploadState.stage}`) }}
              </span>
              <span v-else-if="piUploadState && piUploadState.stage === 'error'" class="text-xs text-red-500">
                {{ t('home.pi.uploadError', { msg: piUploadState.error }) }}
              </span>
              <span v-if="activePiWorkspace" class="text-[11px] text-zinc-400">{{ t('home.pi.activeHint') }}</span>
            </div>
            <input
              ref="piProjectInputEl"
              type="file"
              webkitdirectory
              multiple
              class="hidden"
              @change="handlePiProjectFolderSelected"
            />
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, provide, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getBrowserStorage, readStoredString, writeStoredString, removeStoredKey } from '../stores/browserStorage.js'
import {
  chatEventStream,
  clearSession,
  deleteFileAsset,
  fetchAllSessions,
  finalizeSession,
  getSessionState,
  getFileDownloadUrl,
  newSessionId,
  uploadFileAsset,
  searchSessions,
  QuotaExceededError,
  uploadPiProjectFolder,
  listPiWorkspaces,
  deletePiWorkspace,
  piUndoChange,
  piSaveAllChanges,
  downloadPiWorkspace,
  listPiChanges,
} from '../api/agent.js'
import { isDark as isDarkFn } from '../theme'
import { fetchPlan, fetchProjects, signOut, syncProject } from '../api/account.js'
import {
  getWorkspaceOnboardingComplete,
  setWorkspaceOnboardingComplete,
} from '../stores/workspace.js'
import HomeSidebar from '../components/HomeSidebar.vue'
import OnboardingModal from '../components/OnboardingModal.vue'
import QuotaExceededModal from '../components/QuotaExceededModal.vue'
import SearchBar from '../components/SearchBar.vue'
import ChatTimeline from '../components/timeline/ChatTimeline.vue'
import {
  composeScenarioPrompt,
  resolveTemplateBubbleText,
} from '../utils/scenarioPrompt.js'
import {
  applyTurnEvent,
  hydrateSessionTimeline,
  timelineToChatRows,
} from '../utils/sessionTimeline.js'

const { t, locale, tm } = useI18n()
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

function handleOnboardingScenario(agentHint) {
  const shortcutId = String(agentHint || '').trim()
  if (shortcutItems.value.some((item) => item.id === shortcutId)) {
    activeShortcutId.value = shortcutId
    searchRefHome.value?.focus?.()
  }
  setWorkspaceOnboardingComplete(undefined, true)
  showOnboarding.value = false
}

/** Open one uploaded document in a new browser tab. */
async function openDocumentAttachment(row) {
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

const UI_BY_ID = {
  research: {
    emoji: '\u{1F50D}',
    panel:
      'bg-gradient-to-br from-rose-100 to-rose-50 border-rose-200/80 dark:from-rose-600/40 dark:to-rose-950/55 dark:border-rose-400/20',
  },
  code: {
    emoji: '\u{26A1}',
    panel:
      'bg-gradient-to-br from-amber-100 to-amber-50 border-amber-200/80 dark:from-amber-500/35 dark:to-amber-950/55 dark:border-amber-400/20',
  },
  docs: {
    emoji: '\u{1F4C4}',
    panel:
      'bg-gradient-to-br from-sky-100 to-sky-50 border-sky-200/80 dark:from-sky-500/35 dark:to-sky-950/55 dark:border-sky-400/20',
  },
  chat: {
    emoji: '\u{1F4AC}',
    panel:
      'bg-gradient-to-br from-violet-100 to-violet-50 border-violet-200/80 dark:from-violet-500/40 dark:to-violet-950/55 dark:border-violet-400/20',
  },
  image: {
    emoji: '\u{2728}',
    panel:
      'bg-gradient-to-br from-fuchsia-100 to-fuchsia-50 border-fuchsia-200/80 dark:from-fuchsia-500/35 dark:to-fuchsia-950/55 dark:border-fuchsia-400/20',
  },
  data: {
    emoji: '\u{1F4CA}',
    panel:
      'bg-gradient-to-br from-emerald-100 to-emerald-50 border-emerald-200/80 dark:from-emerald-500/35 dark:to-emerald-950/55 dark:border-emerald-400/20',
  },
  pi: {
    emoji: '\u{1F916}',
    panel:
      'bg-gradient-to-br from-indigo-100 to-indigo-50 border-indigo-200/80 dark:from-indigo-500/35 dark:to-indigo-950/55 dark:border-indigo-400/20',
  },
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
const streamAbortController = ref(null)
/** 中止当前 SSE 流（停止按钮） */
function stopAssistantStream() {
  streamAbortController.value?.abort()
}
/** When true, chat is ephemeral: no history, memory injection, or session finalize. */
const incognitoMode = ref(false)
const scrollEl = ref(null)
const searchRefHome = ref(null)
const searchRefChat = ref(null)
const dark = ref(typeof document !== 'undefined' && document.documentElement.classList.contains('dark'))

// ── 附件状态 ──────────────────────────────────────────────────────────────
const attachmentList = ref([])
const uploading = ref(false)
const uploadError = ref('')
const planSummary = ref(null)
const QUOTA_STREAM_POLL_MS = 30_000
let quotaPollTimer = null
const recentSessions = ref([])
const sessionSearchResults = ref([])
const sessionSearchLoading = ref(false)
let sessionSearchRequestId = 0
const projectRecords = ref([])
const recentProjects = computed(() => {
  return projectRecords.value.map((project) => ({
    id: project.id,
    title: project.title,
    sessions: project.sessions_count,
    assets: project.assets_count,
    updatedAt: project.updated_at,
  }))
})

/** Reset the canonical timeline for a session without touching composer state. */
function resetTimelineState(nextSessionId = sessionId.value) {
  timeline.value = hydrateSessionTimeline({
    session_id: nextSessionId,
    turns: [],
    attachments: attachmentList.value,
  })
}

/** Add a local-only failed turn when the request fails before backend events arrive. */
function appendLocalErrorTurn(message) {
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

async function loadPlanSummary() {
  try {
    planSummary.value = await fetchPlan()
  } catch {
    planSummary.value = null
  }
}

/** Poll plan quota while a chat stream is active so token usage stays current. */
function startQuotaPolling() {
  stopQuotaPolling()
  quotaPollTimer = setInterval(() => {
    loadPlanSummary()
  }, QUOTA_STREAM_POLL_MS)
}

function stopQuotaPolling() {
  if (quotaPollTimer) {
    clearInterval(quotaPollTimer)
    quotaPollTimer = null
  }
}

async function refreshAttachments() {
  // 文件资产由当前会话前端状态持有，旧 session-scoped attachment API 已移除。
}

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])

function extOf(name) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

async function handleFileSelected(file) {
  if (loading.value || uploading.value) return
  const ext = extOf(file.name)
  if (!IMAGE_EXTS.has(ext)) return
  uploading.value = true
  uploadError.value = ''
  try {
    const uploaded = await uploadFileAsset(file)
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
  } catch (err) {
    uploadError.value = err.message || t('chat.uploadFailed')
  } finally {
    uploading.value = false
  }
}

async function deleteAttachment(fileUuid) {
  try {
    await deleteFileAsset(fileUuid)
    attachmentList.value = attachmentList.value.filter((item) => item.file_uuid !== fileUuid)
    await loadPlanSummary()
    await loadSessions()
    await syncCurrentProject()
  } catch (err) {
    uploadError.value = err.message || t('chat.deleteFailed')
  }
}

function resetConversationState() {
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
function scheduleFinalizeSessionIfNeeded(activeSessionId = sessionId.value) {
  if (incognitoMode.value) return
  if (!messages.value.length) return
  void finalizeSession(activeSessionId).catch((err) => {
    console.error('Failed to finalize session memory:', err)
  })
}

/** Start a fresh session; optionally enable or disable incognito mode. */
function startFreshSession({ incognito = false, navigate = true } = {}) {
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
    router.push({ name: 'workspace-session', params: { sessionId: nextSessionId } })
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
function toggleIncognitoMode() {
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
  (name, oldName) => {
    // Guard against killing an in-flight SSE stream: `ensureChatRoute()`
    // (called right when a message is sent) replaces the route from
    // 'workspace' to 'workspace-session', and other internal navigations
    // can transiently report 'workspace' too. Resetting on every such blip
    // used to abort the user's own just-started stream ~instantly, with no
    // visible error (AbortError is swallowed silently below). Only treat
    // this as a genuine "go to a fresh workspace" navigation when the name
    // actually changed AND there's no active stream to protect.
    if (name === 'workspace' && name !== oldName && !streamAbortController.value) {
      resetConversationState()
    }
  },
)

function ensureChatRoute() {
  if (route.name === 'workspace') {
    router.replace({ name: 'workspace-session', params: { sessionId: sessionId.value } })
  }
}

const PILL_BY_ID = {
  research: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-900/40 dark:text-rose-200 dark:ring-rose-400/30',
  code:     'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-400/30',
  docs:     'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-900/40 dark:text-sky-200 dark:ring-sky-400/30',
  chat:     'bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-900/40 dark:text-violet-200 dark:ring-violet-400/30',
  image:    'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200 dark:bg-fuchsia-900/40 dark:text-fuchsia-200 dark:ring-fuchsia-400/30',
  data:     'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200 dark:ring-emerald-400/30',
  pi:       'bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-900/40 dark:text-indigo-200 dark:ring-indigo-400/30',
}

const shortcutItems = computed(() => {
  const raw = tm('home.shortcuts')
  if (!Array.isArray(raw)) return []
  return raw.map((row) => {
    const id = row.id
    const ui = UI_BY_ID[id] || {
      emoji: '\u2728',
      panel:
        'bg-gradient-to-br from-zinc-200 to-zinc-100 border-zinc-300/80 dark:from-zinc-800/80 dark:to-zinc-950/80 dark:border-white/10',
    }
    return {
      id,
      label: row.label,
      role: row.role || row.label,
      summary: row.summary || '',
      taskPreviews: Array.isArray(row.taskPreviews) ? row.taskPreviews : [],
      placeholder: row.placeholder || '',
      home: row.home !== false,
      emoji: ui.emoji,
      panel: ui.panel,
    }
  })
})

const homeShortcutItems = computed(() =>
  shortcutItems.value.filter((item) => item.home !== false),
)

const scenarioTemplates = computed(() => {
  const raw = tm('home.templates')
  if (!Array.isArray(raw)) return []
  const labelById = Object.fromEntries(shortcutItems.value.map((item) => [item.id, item.label]))
  return raw.map((row) => ({
    ...row,
    label: labelById[row.id] || row.title,
    phases: Array.isArray(row.phases) ? row.phases : [],
  }))
})

// Per-session localStorage helpers — key format: icore:pi-mode:{sessionId}
// and icore:pi-ws:{sessionId}. This lets each session independently remember
// which Pi mode and workspace were active so a page refresh restores state.
const _piStorage = getBrowserStorage()
function _piModeKey(sid) { return `icore:pi-mode:${sid}` }
function _piWsKey(sid)   { return `icore:pi-ws:${sid}` }

const activeShortcutId = ref(
  readStoredString(_piStorage, _piModeKey(sessionId.value), ''),
)
watch(activeShortcutId, (val) => {
  writeStoredString(_piStorage, _piModeKey(sessionId.value), val)
})

// --- Pi mode: uploaded-project workspace selection -------------------------
// Lets the user upload a whole project folder and have Pi analyze it inside
// a strictly sandboxed, per-project workspace (server enforces ownership and
// containment — see PiWorkspaceService). `activePiWorkspaceId` travels with
// every chat call while in Pi mode so the backend knows which sandbox to
// extract/point Pi at; it is cleared whenever the user leaves Pi mode.
const piWorkspaces = ref([])
const piWorkspacesLoading = ref(false)
const activePiWorkspaceId = ref(
  readStoredString(_piStorage, _piWsKey(sessionId.value), ''),
)
watch(activePiWorkspaceId, (val) => {
  if (val) writeStoredString(_piStorage, _piWsKey(sessionId.value), val)
  else removeStoredKey(_piStorage, _piWsKey(sessionId.value))
})
const piWorkspacePickerOpen = ref(false)
const piProjectInputEl = ref(null)
const piUploadState = ref(null) // { stage, error? } | null

const activePiWorkspace = computed(
  () => piWorkspaces.value.find((item) => item.id === activePiWorkspaceId.value) || null,
)

async function loadPiWorkspaces() {
  piWorkspacesLoading.value = true
  try {
    piWorkspaces.value = await listPiWorkspaces()
  } catch {
    // Non-fatal — the picker simply shows an empty list; upload still works.
  } finally {
    piWorkspacesLoading.value = false
  }
}

function togglePiWorkspacePicker() {
  piWorkspacePickerOpen.value = !piWorkspacePickerOpen.value
  if (piWorkspacePickerOpen.value && !piWorkspaces.value.length) {
    loadPiWorkspaces()
  }
}

function selectPiWorkspace(workspace) {
  activePiWorkspaceId.value = workspace?.id || ''
  piWorkspacePickerOpen.value = false
}

function clearActivePiWorkspace() {
  activePiWorkspaceId.value = ''
  piWorkspacePickerOpen.value = false
}

async function removePiWorkspace(workspace) {
  if (!workspace?.id) return
  try {
    await deletePiWorkspace(workspace.id)
    piWorkspaces.value = piWorkspaces.value.filter((item) => item.id !== workspace.id)
    if (activePiWorkspaceId.value === workspace.id) clearActivePiWorkspace()
  } catch {
    // Leave the list as-is; user can retry from the picker.
  }
}

function triggerPiProjectUpload() {
  piWorkspacePickerOpen.value = false
  piProjectInputEl.value?.click()
}

async function handlePiProjectFolderSelected(event) {
  const files = Array.from(event?.target?.files || [])
  if (event?.target) event.target.value = ''
  if (!files.length) return

  const firstRelPath = files[0]?.webkitRelativePath || files[0]?.name || ''
  const projectTitle = firstRelPath.split('/')[0] || 'Untitled project'

  piUploadState.value = { stage: 'zipping' }
  try {
    const workspace = await uploadPiProjectFolder(files, projectTitle, (progress) => {
      piUploadState.value = { stage: progress.stage }
    })
    piWorkspaces.value = [workspace, ...piWorkspaces.value.filter((item) => item.id !== workspace.id)]
    activePiWorkspaceId.value = workspace.id
    piUploadState.value = null
  } catch (err) {
    piUploadState.value = { stage: 'error', error: err?.message || String(err) }
  }
}

// Leaving Pi mode clears the active project — re-entering starts fresh and
// the user explicitly re-selects which project Pi should see.
watch(activeShortcutId, (next, prev) => {
  if (next === 'pi' && prev !== 'pi') {
    loadPiWorkspaces()
  }
  if (prev === 'pi' && next !== 'pi') {
    activePiWorkspaceId.value = ''
    piWorkspacePickerOpen.value = false
  }
})

const activeShortcut = computed(
  () => shortcutItems.value.find((it) => it.id === activeShortcutId.value) || null,
)
const activeScenarioTemplate = computed(
  () => scenarioTemplates.value.find((it) => it.id === activeShortcutId.value) || null,
)

const templateLabelById = computed(() =>
  Object.fromEntries(shortcutItems.value.map((item) => [item.id, item.label])),
)
const activeShortcutPill = computed(() => {
  const it = activeShortcut.value
  if (!it) return null
  const projectName = it.id === 'pi' ? activePiWorkspace.value?.title || '' : ''
  return {
    label: projectName ? `${it.label} · ${projectName}` : it.label,
    emoji: it.emoji,
    pillClass: PILL_BY_ID[it.id] || '',
  }
})

const quotaItems = computed(() => {
  const usage = planSummary.value?.usage || {}
  const limits = planSummary.value?.limits || {}
  const formatLimit = (value) => (value == null ? '∞' : value)
  const items = [
    { label: t('home.quota.tokens'), value: `${usage.tokens ?? 0}` },
    { label: t('home.quota.attachments'), value: `${usage.attachments ?? 0}/${formatLimit(limits.attachments)}` },
  ]
  if (limits.tasks !== null && limits.tasks !== undefined) {
    items.unshift({ label: t('home.quota.tasks'), value: `${usage.tasks ?? 0}/${formatLimit(limits.tasks)}` })
  }
  return items
})

function syncTheme() {
  dark.value = isDarkFn()
}

onMounted(async () => {
  syncTheme()
  window.addEventListener('icore-theme-change', syncTheme)
  await loadSessions()
  loadPlanSummary()
  loadProjects()
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
    // Restore Pi mode/workspace for the new session from localStorage (or reset)
    activeShortcutId.value = readStoredString(_piStorage, _piModeKey(resolved), '')
    activePiWorkspaceId.value = readStoredString(_piStorage, _piWsKey(resolved), '')
    await loadPlanSummary()
    await hydrateCurrentSession()
  },
)

watch(
  () => [messages.value.length, loading.value],
  () => {
    if (loading.value) {
      scrollBottom()
    }
  },
)

async function scrollBottom() {
  await nextTick()
  if (messages.value.length > 0) {
    await nextTick()
  }
  await new Promise((resolve) => {
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
function applyChatScrollBottom() {
  const el = scrollEl.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

/** Whether the chat scroll container is already at (or very near) its bottom edge. */
function isChatScrollNearBottom(thresholdPx = 120) {
  const el = scrollEl.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight <= thresholdPx
}

/**
 * The composer grows taller as the user types multi-line messages. Its
 * wrapper sits at the bottom of the same flex column as the message list, so
 * a taller composer shrinks the list's visible height — without re-syncing
 * scroll position, the latest message ends up sliding behind the composer.
 * Re-pin to the bottom only when the user was already reading the latest
 * messages, so scrolling through history isn't interrupted.
 */
function handleComposerResize() {
  if (!isChatScrollNearBottom()) return
  requestAnimationFrame(() => applyChatScrollBottom())
}

// 前端 shortcut id → 后端 agent_hint 映射。docs 按钮走 knowledge_agent。
const SHORTCUT_HINT = {
  research: 'research',
  code: 'chat',
  docs: 'knowledge',
  chat: 'chat',
  image: 'image',
  data: 'data',
  pi:   'pi',
}

function mapSessionSummary(item) {
  const count = Number(item.turn_count ?? item.message_count ?? 0)
  return {
    sessionId: item.public_id,
    title: (item.title || '').trim() || t('home.heroTitle'),
    subtitle: t('home.recent.messages', { count }),
    updatedAt: item.updated_at,
    messageCount: count,
  }
}

async function loadSessions() {
  try {
    const { sessions } = await fetchAllSessions()
    recentSessions.value = sessions.map(mapSessionSummary)
  } catch {
    recentSessions.value = []
  }
}

async function onDeleteSession(deletedSessionId) {
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

function mapSearchResult(item) {
  return {
    sessionId: item.public_id,
    title: (item.title || '').trim() || t('home.heroTitle'),
    snippet: item.snippet || '',
    updatedAt: item.updated_at,
    rank: item.rank,
  }
}

/** Run sidebar session search against the backend full-text index. */
async function onSessionSearch(query) {
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

async function loadProjects() {
  try {
    const payload = await fetchProjects()
    projectRecords.value = payload.projects || []
  } catch {
    projectRecords.value = []
  }
}

async function syncCurrentProject(meta = {}) {
  const template = activeScenarioTemplate.value
  const projectId = meta.projectId || template?.id || 'general'
  const projectTitle = meta.projectTitle || template?.title || t('home.heroTitle')
  const sessionTitle = meta.sessionTitle || meta.title || template?.title || t('home.heroTitle')
  const sessionSubtitle = meta.sessionSubtitle || meta.subtitle || template?.description || t('home.subtitle')
  try {
    await syncProject({
      project_id: projectId,
      project_title: projectTitle,
      scenario_id: template?.id || meta.scenarioId || '',
      session_id: sessionId.value,
      session_title: sessionTitle,
      session_subtitle: sessionSubtitle,
      attachment_count: Number(meta.attachmentCount ?? attachmentList.value.length ?? 0),
    })
    await loadProjects()
  } catch {
    // Keep local continuity even if remote sync fails.
  }
}

async function hydrateCurrentSession() {
  const hasExplicitSession = typeof route.params.sessionId === 'string'
  if (!hasExplicitSession) {
    await refreshAttachments()
    return
  }
  try {
    const state = await getSessionState(sessionId.value)
    attachmentList.value = state.attachments || []
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
    // Restore Pi file changes: if this session had Pi mode active, fetch any
    // pending changes from pi-source-service and attach them to the last
    // assistant message so Undo / Save All / Download buttons reappear.
    const restoredWsId = activePiWorkspaceId.value
      || readStoredString(_piStorage, _piWsKey(sessionId.value), '')
    if (restoredWsId) {
      try {
        const { changes } = await listPiChanges(sessionId.value)
        if (changes?.length) {
          // Find the last assistant message and attach all changes to it
          const lastAssistIdx = [...messages.value].reverse().findIndex((m) => m.role === 'assistant')
          if (lastAssistIdx !== -1) {
            const realIdx = messages.value.length - 1 - lastAssistIdx
            messages.value[realIdx] = {
              ...messages.value[realIdx],
              fileChanges: changes.map((c) => ({ ...c, undone: false })),
            }
          }
        }
      } catch {
        // Non-fatal — changes just won't show after refresh
      }
    }
    if (messages.value.length > 0) {
      await scrollBottom()
    }
  } catch {
    await refreshAttachments()
  }
}

function buildTemplateSendPayload(userQuery) {
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
    bubbleText: resolveTemplateBubbleText(activeShortcut.value?.label, query),
    agentMessage: composeScenarioPrompt(query, template),
    templateId: activeShortcutId.value || template.id || '',
  }
}

async function sendUserMessage(msg, agentHint = '', {
  skipUserBubble = false,
  displayCaption = '',
  turnFileUuids = null,
} = {}) {
  const text = String(msg ?? '').trim()
  if (!text || loading.value) return
  const { bubbleText, agentMessage, templateId } = buildTemplateSendPayload(text)
  const captionForApi = String(displayCaption || '').trim()
  const fileUuids = Array.isArray(turnFileUuids)
    ? turnFileUuids.map((item) => String(item || '').trim()).filter(Boolean)
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
      ...(activeShortcutId.value === 'pi' && activePiWorkspaceId.value
        ? { piWorkspaceId: activePiWorkspaceId.value }
        : {}),
      incognito: incognitoMode.value,
    })) {
      if (!evt) continue
      applyTurnEvent(timeline.value, evt)
      await scrollBottom()
    }
  } catch (e) {
    const aborted = typeof e?.name === 'string' && e.name === 'AbortError'
    if (!aborted) {
      if (e instanceof QuotaExceededError) {
        // 超出 Token 配额 → 显示升级弹窗，而不是报错
        quotaExceededPlan.value = e.currentPlan
        showQuotaModal.value = true
      } else {
        const errorMsg = String(e?.message || '')
        if (errorMsg.includes('401')) {
          signOut()
          router.push({ name: 'auth' })
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

// ---------------------------------------------------------------------------
// Pi Agent file-change actions — Undo and Save All
// ---------------------------------------------------------------------------

async function handlePiUndo(msg, change) {
  if (!change || change.undone || change.savedAt > 0) return
  try {
    await piUndoChange(sessionId.value, change.changeId)
    // Mark as undone in the message so the UI updates immediately
    const msgIdx = messages.value.findIndex((m) => m.id === msg.id)
    if (msgIdx !== -1) {
      const updated = {
        ...messages.value[msgIdx],
        fileChanges: messages.value[msgIdx].fileChanges.map((c) =>
          c.changeId === change.changeId ? { ...c, undone: true } : c,
        ),
      }
      messages.value[msgIdx] = updated
    }
  } catch (e) {
    console.error('Pi undo failed', e)
  }
}

async function handlePiSaveAll(msg) {
  if (!msg.fileChanges?.length) return
  const unsaved = msg.fileChanges.filter((c) => !c.undone && c.savedAt === 0)
  if (!unsaved.length) return
  try {
    await piSaveAllChanges(sessionId.value)
    // Mark all pending changes for this message as saved
    const now = Date.now()
    const msgIdx = messages.value.findIndex((m) => m.id === msg.id)
    if (msgIdx !== -1) {
      const updated = {
        ...messages.value[msgIdx],
        fileChanges: messages.value[msgIdx].fileChanges.map((c) =>
          c.savedAt === 0 && !c.undone ? { ...c, savedAt: now } : c,
        ),
      }
      messages.value[msgIdx] = updated
    }
  } catch (e) {
    console.error('Pi save-all failed', e)
  }
}

async function handlePiDownload() {
  if (!sessionId.value) return
  try {
    await downloadPiWorkspace(sessionId.value)
  } catch (e) {
    console.error('Pi download failed', e)
  }
}

async function handleSubmit({ message, imageFiles, dataFiles }) {
  if (loading.value || uploading.value) return
  const hint = SHORTCUT_HINT[activeShortcutId.value] || ''
  const text = (message || '').trim()
  const imgs = Array.isArray(imageFiles) ? imageFiles.filter((f) => f && f.size) : []
  const datas = Array.isArray(dataFiles) ? dataFiles.filter((f) => f && f.size) : []

  if (!imgs.length && !datas.length) {
    if (text) await sendUserMessage(text, hint)
    return
  }

  uploadError.value = ''
  uploading.value = true
  try {
    const uploadedImages = []
    for (const imageFile of imgs) {
      const uploaded = await uploadFileAsset(imageFile)
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
    const uploadedDataMeta = []
    for (const df of datas) {
      const meta = await uploadFileAsset(df)
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
  } catch (err) {
    uploadError.value = err.message || t('chat.uploadFailed')
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

function toggleShortcut(id) {
  activeShortcutId.value = activeShortcutId.value === id ? '' : id
  nextTick(() => {
    ;(isChatRoute.value ? searchRefChat.value : searchRefHome.value)?.focus?.()
  })
}

function setComposerMode(id) {
  activeShortcutId.value = id
  nextTick(() => {
    ;(isChatRoute.value ? searchRefChat.value : searchRefHome.value)?.focus?.()
  })
}

function clearShortcut() {
  activeShortcutId.value = ''
}

function applyStarter(starter) {
  const hint = SHORTCUT_HINT[activeShortcutId.value] || ''
  sendUserMessage(starter, hint)
}

function startShortcutTask(id, task) {
  activeShortcutId.value = id
  const hint = SHORTCUT_HINT[id] || ''
  sendUserMessage(task, hint)
}

function openRecentSession(targetSessionId) {
  router.push({ name: 'workspace-session', params: { sessionId: targetSessionId } })
}

function onSidebarNew() {
  if (!incognitoMode.value) {
    scheduleFinalizeSessionIfNeeded()
  }
  startFreshSession({ incognito: false })
  syncCurrentProject({
    title: activeScenarioTemplate.value?.title || t('home.heroTitle'),
    subtitle: t('home.subtitle'),
  })
}

function goAccount() {
  router.push({ name: 'account' })
}

function handleSignOut() {
  signOut()
  router.push({ name: 'auth' })
}
</script>
