<template>
  <div
    class="flex h-screen min-h-0 bg-zinc-100 text-zinc-950 antialiased transition-colors duration-300 ease-out dark:bg-zinc-950 dark:text-zinc-100"
  >
    <OnboardingModal :show="showOnboarding" @select-scenario="handleOnboardingScenario" @close="showOnboarding = false" />

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
      @new="onSidebarNew"
      @navigate="sidebarMobileOpen = false"
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
        class="relative z-10 flex shrink-0 items-center justify-between gap-3 px-4 py-4 sm:px-8"
      >
        <div class="hidden items-center gap-2 md:flex">
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
        <!-- 移动端汉堡菜单按钮（桌面端隐藏） -->
        <button
          type="button"
          class="-ml-1 mr-auto flex rounded-xl p-2 text-zinc-600 transition-colors hover:bg-zinc-200/80 hover:text-zinc-950 lg:hidden dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
          :aria-label="t('home.sidebar.openMenu')"
          @click="sidebarMobileOpen = true"
        >
          <svg class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <button
          type="button"
          @click="goAccount"
          class="rounded-full px-4 py-2 text-sm font-medium text-zinc-700 transition-colors duration-300 hover:bg-zinc-200/80 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
        >
          {{ t('home.accountCenter') }}
        </button>
        <button
          type="button"
          @click="handleSignOut"
          class="rounded-full bg-zinc-950 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-zinc-900/20 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] dark:bg-white dark:text-zinc-950 dark:shadow-black/30"
        >
          {{ t('home.signOut') }}
        </button>
      </header>

      <main class="relative z-10 flex min-h-0 flex-1 flex-col">
        <div class="flex min-h-0 flex-1 flex-col">
          <div
            v-if="isChatRoute && messages.length > 0"
            ref="scrollEl"
            class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-6 sm:px-6"
          >
            <div class="mx-auto w-full max-w-3xl space-y-6">
              <div
                v-for="msg in messages"
                :key="msg.id"
                v-show="msg.role === 'user' || msg.content || (msg.steps && msg.steps.length)"
                :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
              >
                <div
                  v-if="msg.role === 'user'"
                  :class="[
                    'rounded-2xl rounded-tr-sm text-sm leading-relaxed ring-1 transition-colors duration-300',
                    userBubbleUsesAttachLayout(msg)
                      ? 'shadow-sm shadow-zinc-900/5 dark:shadow-md dark:shadow-black/20'
                      : 'shadow-md shadow-zinc-900/8 dark:shadow-lg dark:shadow-black/25',
                    'bg-white text-zinc-900 ring-zinc-200/90',
                    'dark:bg-zinc-800 dark:text-zinc-100 dark:ring-white/10',
                    userBubbleUsesAttachLayout(msg)
                      ? 'w-fit max-w-[min(24rem,calc(100vw-2.5rem))] px-2 py-1.5'
                      : 'max-w-[70%] px-4 py-3',
                  ]"
                >
                  <template v-if="msg.type === 'image'">
                    <template v-for="imgItems in [userImageList(msg)]" :key="`${msg.id}-imglist`">
                      <div v-if="imgItems.length" class="flex flex-col gap-1.5">
                        <div class="flex flex-wrap items-end gap-1.5">
                          <a
                            v-for="(im, idx) in imgItems"
                            :key="(im.filename || 'img') + '-' + idx"
                            :href="im.content"
                            target="_blank"
                            rel="noopener noreferrer"
                            :title="`${im.filename || t('chat.imageUntitled')} — ${t('chat.openImageFullSize')}`"
                            :aria-label="`${t('chat.openImageFullSize')}: ${im.filename || t('chat.imageUntitled')}`"
                            class="block h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-zinc-200/90 shadow-sm ring-1 ring-zinc-200/80 outline-none transition hover:ring-violet-400/50 focus-visible:ring-2 focus-visible:ring-violet-500/60 dark:bg-zinc-700/50 dark:ring-white/10 dark:hover:ring-violet-400/35"
                          >
                            <img
                              :src="im.content"
                              :alt="imageItemAlt(im.filename)"
                              class="h-full w-full object-cover"
                              loading="lazy"
                            />
                          </a>
                        </div>
                        <p
                          v-if="msg.caption"
                          class="max-w-full whitespace-pre-wrap break-words border-t border-zinc-200/80 pt-1.5 text-sm leading-snug text-zinc-800 dark:border-white/10 dark:text-white/95"
                        >
                          {{ msg.caption }}
                        </p>
                      </div>
                    </template>
                  </template>
                  <template v-else-if="msg.type === 'data'">
                    <div class="flex flex-col gap-1.5">
                      <div class="flex flex-wrap items-end gap-1.5">
                        <div
                          v-for="(row, idx) in (msg.dataAttachments || [])"
                          :key="(row.filename || 'data') + '-' + idx"
                          class="flex h-14 max-w-[11rem] shrink-0 items-center gap-2 rounded-lg border border-zinc-200/90 bg-zinc-50 px-2.5 shadow-sm ring-1 ring-zinc-200/70 dark:border-white/10 dark:bg-zinc-900/50 dark:ring-white/10"
                          :title="row.filename"
                        >
                          <svg class="h-7 w-7 shrink-0 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24" aria-hidden="true">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span class="min-w-0 flex-1 truncate text-[11px] font-medium leading-tight text-zinc-800 dark:text-zinc-200">
                            {{ row.filename }}
                          </span>
                        </div>
                      </div>
                      <p
                        v-if="msg.caption"
                        class="max-w-full whitespace-pre-wrap break-words border-t border-zinc-200/80 pt-1.5 text-sm leading-snug text-zinc-800 dark:border-white/10 dark:text-white/95"
                      >
                        {{ msg.caption }}
                      </p>
                    </div>
                  </template>
                  <template v-else-if="msg.type === 'composite'">
                    <div class="flex flex-col gap-1.5">
                      <div v-if="userImageList(msg).length" class="flex flex-wrap items-end gap-1.5">
                        <a
                          v-for="(im, idx) in userImageList(msg)"
                          :key="(im.filename || 'img') + '-' + idx"
                          :href="im.content"
                          target="_blank"
                          rel="noopener noreferrer"
                          :title="`${im.filename || t('chat.imageUntitled')} — ${t('chat.openImageFullSize')}`"
                          :aria-label="`${t('chat.openImageFullSize')}: ${im.filename || t('chat.imageUntitled')}`"
                          class="block h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-zinc-200/90 shadow-sm ring-1 ring-zinc-200/80 outline-none transition hover:ring-violet-400/50 focus-visible:ring-2 focus-visible:ring-violet-500/60 dark:bg-zinc-700/50 dark:ring-white/10 dark:hover:ring-violet-400/35"
                        >
                          <img
                            :src="im.content"
                            :alt="imageItemAlt(im.filename)"
                            class="h-full w-full object-cover"
                            loading="lazy"
                          />
                        </a>
                      </div>
                      <div v-if="msg.dataAttachments?.length" class="flex flex-wrap items-end gap-1.5">
                        <div
                          v-for="(row, idx) in msg.dataAttachments"
                          :key="(row.filename || 'data') + '-' + idx"
                          class="flex h-14 max-w-[11rem] shrink-0 items-center gap-2 rounded-lg border border-zinc-200/90 bg-zinc-50 px-2.5 shadow-sm ring-1 ring-zinc-200/70 dark:border-white/10 dark:bg-zinc-900/50 dark:ring-white/10"
                          :title="row.filename"
                        >
                          <svg class="h-7 w-7 shrink-0 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24" aria-hidden="true">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span class="min-w-0 flex-1 truncate text-[11px] font-medium leading-tight text-zinc-800 dark:text-zinc-200">
                            {{ row.filename }}
                          </span>
                        </div>
                      </div>
                      <p
                        v-if="msg.caption"
                        class="max-w-full whitespace-pre-wrap break-words border-t border-zinc-200/80 pt-1.5 text-sm leading-snug text-zinc-800 dark:border-white/10 dark:text-white/95"
                      >
                        {{ msg.caption }}
                      </p>
                    </div>
                  </template>
                  <template v-else>
                    {{ msg.content }}
                  </template>
                </div>
                <div v-else class="flex max-w-[80%] gap-3">
                  <div
                    class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-xs font-bold text-white shadow-md shadow-violet-900/20 dark:shadow-violet-900/40"
                  >
                    A
                  </div>
                  <div class="flex min-w-0 flex-1 flex-col gap-2">
                    <div
                      v-if="msg.steps && msg.steps.length"
                      class="rounded-xl border border-zinc-200/90 bg-white/70 px-3 py-2 text-xs ring-1 ring-black/5 dark:border-white/[0.08] dark:bg-zinc-900/40 dark:ring-white/10"
                    >
                      <button
                        type="button"
                        class="flex w-full items-center gap-1.5 text-left text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                        @click="msg.stepsCollapsed = !msg.stepsCollapsed"
                      >
                        <span class="transition-transform" :class="msg.stepsCollapsed ? '' : 'rotate-90'">▸</span>
                        <span>
                          {{ msg.streaming
                            ? t('chat.stepsLive', { n: msg.steps.length })
                            : t('chat.stepsCollapsed', { n: msg.steps.length }) }}
                        </span>
                      </button>
                      <ul
                        v-if="!msg.stepsCollapsed"
                        class="mt-2 space-y-1 border-l border-zinc-200 pl-3 dark:border-white/10"
                      >
                        <li
                          v-for="s in msg.steps"
                          :key="s.step"
                          class="text-zinc-600 dark:text-zinc-400"
                        >
                          <span class="font-medium text-zinc-700 dark:text-zinc-300">{{ s.step }}. {{ s.tool }}</span>
                          <span v-if="s.input_preview" class="ml-1 text-zinc-500 dark:text-zinc-500">— {{ s.input_preview }}</span>
                        </li>
                      </ul>
                    </div>
                    <div
                      :class="[
                        'rounded-2xl rounded-tl-sm border px-4 py-3 text-sm leading-relaxed shadow-md ring-1 transition-colors duration-300 dark:shadow-lg dark:backdrop-blur-sm',
                        'border-zinc-200/90 bg-white text-zinc-950 ring-black/5 dark:border-white/[0.08] dark:bg-zinc-900/60 dark:text-zinc-200 dark:shadow-black/25 dark:ring-white/10',
                        dark ? 'prose-chat-dark' : 'prose-chat',
                        msg.streaming ? (dark ? 'typing-cursor typing-cursor-dark' : 'typing-cursor') : '',
                      ]"
                      v-html="renderMarkdown(msg.content)"
                    />
                  </div>
                </div>
              </div>

              <div
                v-if="loading && (!streamingMsg || (!streamingMsg.content && !(streamingMsg.steps && streamingMsg.steps.length)))"
                class="flex justify-start gap-3"
              >
                <div
                  class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600"
                >
                  <span class="text-xs font-bold text-white">A</span>
                </div>
                <div
                  class="flex items-center gap-1 rounded-2xl border border-zinc-200/90 bg-white px-4 py-3 shadow-md ring-1 ring-black/5 transition-colors duration-300 dark:border-white/[0.08] dark:bg-zinc-900/60 dark:shadow-lg dark:shadow-black/20 dark:ring-white/10"
                >
                  <span
                    v-for="i in 3"
                    :key="i"
                    class="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 dark:bg-zinc-500"
                    :style="{ animationDelay: `${(i - 1) * 0.15}s` }"
                  />
                </div>
              </div>
            </div>
          </div>

          <div
            v-else-if="isChatRoute && messages.length === 0"
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
            <div class="flex w-full max-w-3xl flex-col items-center text-center">
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
                  class="max-w-md text-sm leading-relaxed text-zinc-600 sm:text-base dark:text-zinc-400"
                >
                  {{ t('home.subtitle') }}
                </p>
              </div>

              <div class="mt-6 w-full">
                <SearchBar
                  ref="searchRefHome"
                  :placeholder="activeShortcut?.placeholder || ''"
                  :mode-pill="activeShortcutPill"
                  :mode-menu-items="shortcutItems"
                  :active-mode-id="activeShortcutId"
                  :streaming="loading"
                  :send-blocked="uploading"
                  @submit="handleSubmit"
                  @stop="stopAssistantStream"
                  @file-selected="handleFileSelected"
                  @clear-mode="clearShortcut"
                  @select-mode="setComposerMode"
                />

                <!-- 附件列表（首页）：会话中的文档/RAG 等；图片与数据文件仅在气泡内展示 -->
                <div v-if="composerAttachments.length || uploading" class="mt-2 flex flex-wrap gap-2 justify-center">
                  <div
                    v-for="att in composerAttachments"
                    :key="att.filename"
                    class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                           border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
                  >
                    <svg class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                    <span class="max-w-[160px] truncate">{{ att.filename }}</span>
                    <span :class="att.mode === 'rag'
                      ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                      : att.mode === 'data'
                      ? 'rounded bg-emerald-100 px-1 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                      : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'">
                      {{ att.mode === 'rag' ? t('chat.attachmentRag') : att.mode === 'data' ? t('chat.attachmentData') : t('chat.attachmentInline') }}
                    </span>
                    <button @click="deleteAttachment(att.filename)" class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400">
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

              <div
                class="mt-6 flex max-w-3xl flex-wrap items-start justify-center gap-x-4 gap-y-6 sm:gap-x-6 sm:gap-y-8"
              >
                <button
                  v-for="item in shortcutItems"
                  :key="item.id"
                  type="button"
                  :disabled="loading"
                  :aria-pressed="activeShortcutId === item.id"
                  @click="toggleShortcut(item.id)"
                  class="group flex w-[4.5rem] flex-col items-center gap-2.5 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-100 disabled:opacity-50 dark:focus-visible:ring-violet-400/40 dark:focus-visible:ring-offset-zinc-950 sm:w-[5.25rem]"
                >
                  <span
                    :class="[
                      'flex h-12 w-12 items-center justify-center rounded-2xl border text-lg shadow-md ring-1 transition-all duration-300 ease-out group-hover:scale-110 group-hover:shadow-lg motion-reduce:transition-colors motion-reduce:group-hover:scale-100 sm:h-14 sm:w-14 sm:text-xl dark:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.5)] dark:group-hover:shadow-[0_16px_32px_-8px_rgba(0,0,0,0.55)]',
                      item.panel,
                      activeShortcutId === item.id
                        ? 'scale-110 ring-2 ring-violet-500 ring-offset-2 ring-offset-zinc-100 dark:ring-violet-400 dark:ring-offset-zinc-950'
                        : 'ring-black/5 group-hover:ring-black/10 dark:ring-white/10',
                    ]"
                  >
                    {{ item.emoji }}
                  </span>
                  <span
                    :class="[
                      'max-w-[5.5rem] text-center text-[11px] font-medium leading-tight transition-colors duration-200 sm:text-xs',
                      activeShortcutId === item.id
                        ? 'text-violet-600 dark:text-violet-300'
                        : 'text-zinc-600 group-hover:text-zinc-950 dark:text-zinc-400 dark:group-hover:text-zinc-200',
                    ]"
                  >
                    {{ item.label }}
                  </span>
                </button>
              </div>

              <div
                v-if="activeScenarioTemplate"
                class="mt-8 w-full rounded-[1.75rem] border border-zinc-200/80 bg-white/80 p-5 text-left shadow-sm dark:border-white/10 dark:bg-white/[0.05]"
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

                <div class="mt-5 grid gap-4 md:grid-cols-2">
                  <div class="rounded-2xl bg-zinc-50 p-4 dark:bg-white/[0.04]">
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
                  <div class="rounded-2xl bg-zinc-50 p-4 dark:bg-white/[0.04]">
                    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
                      {{ t('home.scenario.outputs') }}
                    </p>
                    <ul class="mt-3 space-y-2 text-sm text-zinc-600 dark:text-zinc-300">
                      <li v-for="output in activeScenarioTemplate.outputs" :key="output">• {{ output }}</li>
                    </ul>
                  </div>
                </div>

                <div class="mt-5">
                  <p class="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
                    {{ t('home.scenario.starters') }}
                  </p>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <button
                      v-for="starter in activeScenarioTemplate.starters"
                      :key="starter"
                      type="button"
                      class="rounded-full border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-600 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-300 dark:hover:text-white"
                      @click="applyStarter(starter)"
                    >
                      {{ starter }}
                    </button>
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
            class="relative z-30 shrink-0 border-t border-zinc-200 bg-zinc-100/85 p-4 backdrop-blur-md transition-all duration-500 ease-in-out dark:border-white/10 dark:bg-zinc-950 dark:backdrop-blur-none sm:px-8"
          >
            <!-- 附件列表（对话模式）：文档/RAG 等；图片与数据文件仅在气泡内展示 -->
            <div v-if="composerAttachments.length || uploading || uploadError" class="mx-auto max-w-3xl mb-2">
              <div v-if="composerAttachments.length || uploading" class="flex flex-wrap gap-2">
                <div
                  v-for="att in composerAttachments"
                  :key="att.filename"
                  class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium
                         border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-white/10 dark:bg-zinc-800/60 dark:text-zinc-300"
                >
                  <svg class="h-3.5 w-3.5 shrink-0 text-violet-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                  </svg>
                  <span class="max-w-[160px] truncate">{{ att.filename }}</span>
                  <span :class="att.mode === 'rag'
                    ? 'rounded bg-amber-100 px-1 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                    : att.mode === 'data'
                    ? 'rounded bg-emerald-100 px-1 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : 'rounded bg-violet-100 px-1 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300'">
                    {{ att.mode === 'rag' ? t('chat.attachmentRag') : att.mode === 'data' ? t('chat.attachmentData') : t('chat.attachmentInline') }}
                  </span>
                  <button @click="deleteAttachment(att.filename)" class="ml-0.5 rounded p-0.5 text-zinc-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400">
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
              @submit="handleSubmit"
              @stop="stopAssistantStream"
              @file-selected="handleFileSelected"
              @clear-mode="clearShortcut"
              @select-mode="setComposerMode"
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
import { marked } from 'marked'
import {
  chatStream,
  getSessionState,
  newSessionId,
  attachFile,
  attachImage,
  attachData,
  imageUrl,
  listAttachments,
  removeAttachment,
} from '../api/agent.js'
import { isDark as isDarkFn } from '../theme'
import { fetchPlan, fetchProjects, signOut, syncProject } from '../api/account.js'
import HomeSidebar from '../components/HomeSidebar.vue'
import OnboardingModal from '../components/OnboardingModal.vue'
import SearchBar from '../components/SearchBar.vue'

const { t, locale, tm } = useI18n()
const route = useRoute()
const router = useRouter()

const isHomeRoute = computed(() => route.name === 'workspace')
const isChatRoute = computed(() => route.name === 'workspace-session')

// 移动端侧边栏开关状态
const sidebarMobileOpen = ref(false)

// Onboarding: 首次访问时弹出场景选择引导
const showOnboarding = ref(false)
const ONBOARDING_KEY = 'icore_onboarding_completed'

onMounted(() => {
  const completed = localStorage.getItem(ONBOARDING_KEY)
  if (!completed && !route.params.sessionId) {
    // 延迟 500ms 弹出，让用户先看到工作台界面
    setTimeout(() => {
      showOnboarding.value = true
    }, 500)
  }
})

function handleOnboardingScenario(agentHint) {
  // 用户选择场景后，自动填充对应的 agent hint
  const scenario = scenarios.value.find(s => s.agentHint === agentHint)
  if (scenario) {
    activeShortcutId.value = agentHint
    searchRefHome.value?.focus?.()
  }
  localStorage.setItem(ONBOARDING_KEY, 'true')
  showOnboarding.value = false
}

marked.setOptions({ breaks: true, gfm: true })

function imageItemAlt(filename) {
  if (filename) return t('chat.imageUploadedAlt', { name: filename })
  return t('chat.imageUploadedAltGeneric')
}

/** @param {{ images?: Array<{ content: string, filename?: string }>, content?: string, filename?: string, type?: string }} msg */
function userImageList(msg) {
  if (msg?.images?.length) return msg.images
  if ((msg?.type === 'image' || msg?.type === 'composite') && msg?.content) {
    return [{ content: msg.content, filename: msg.filename }]
  }
  return []
}

/** 用户气泡是否采用「附件」紧凑布局（图片 / 数据文件 / 混合） */
function userBubbleUsesAttachLayout(msg) {
  if (msg?.role !== 'user') return false
  if (msg.type === 'image') return userImageList(msg).length > 0
  if (msg.type === 'data') return (msg.dataAttachments?.length ?? 0) > 0
  if (msg.type === 'composite') {
    return userImageList(msg).length > 0 || (msg.dataAttachments?.length ?? 0) > 0
  }
  return false
}

function renderMarkdown(text) {
  if (!text) return '&nbsp;'
  return marked.parse(text)
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
}

const messages = ref([])
const loading = ref(false)
/** 中止当前 /chat SSE（用户点击停止） */
const streamAbortController = ref(null)
const streamingMsg = ref(null)
/** 中止当前 SSE 流（停止按钮） */
function stopAssistantStream() {
  streamAbortController.value?.abort()
}
const sessionId = ref(typeof route.params.sessionId === 'string' ? route.params.sessionId : newSessionId())
const scrollEl = ref(null)
const searchRefHome = ref(null)
const searchRefChat = ref(null)
const dark = ref(typeof document !== 'undefined' && document.documentElement.classList.contains('dark'))

// ── 附件状态 ──────────────────────────────────────────────────────────────
const attachmentList = ref([])
const uploading = ref(false)
const uploadError = ref('')
const planSummary = ref(null)
const recentSessions = ref([])
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

const RECENT_SESSIONS_KEY = 'icore_recent_sessions'

/** 输入区只展示文档等非图片、非数据会话附件；图片与数据文件仅在对话气泡中展示 */
const composerAttachments = computed(() =>
  attachmentList.value.filter((a) => a.mode !== 'image' && a.mode !== 'data'),
)

async function refreshAttachments() {
  try {
    attachmentList.value = await listAttachments(sessionId.value)
  } catch { /* 静默失败 */ }
}

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'])

function extOf(name) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

async function handleFileSelected(file) {
  if (loading.value || uploading.value) return
  uploading.value = true
  uploadError.value = ''
  try {
    const ext = extOf(file.name)
    if (IMAGE_EXTS.has(ext)) {
      const { ref: imageRef, filename: savedName } = await attachImage(file, sessionId.value)
      await refreshAttachments()
      const url = imageUrl(imageRef)
      if (url) {
        messages.value.push({
          id: `${Date.now()}-u`,
          role: 'user',
          type: 'image',
          images: [{ content: url, filename: savedName || file.name }],
        })
        ensureChatRoute()
        await scrollBottom()
        const hint = SHORTCUT_HINT[activeShortcutId.value] || ''
        if (!loading.value) {
          await sendUserMessage(t('chat.imageReplyPrompt'), hint, { skipUserBubble: true })
        }
      }
    } else {
      await attachFile(file, sessionId.value)
      await refreshAttachments()
    }
    saveRecentSession()
    await syncCurrentProject()
  } catch (err) {
    uploadError.value = err.message || t('chat.uploadFailed')
  } finally {
    uploading.value = false
  }
}

async function deleteAttachment(filename) {
  try {
    await removeAttachment(sessionId.value, filename)
    await refreshAttachments()
    saveRecentSession()
    await syncCurrentProject()
  } catch (err) {
    uploadError.value = err.message || t('chat.deleteFailed')
  }
}

function resetConversationState() {
  stopAssistantStream()
  messages.value = []
  sessionId.value = newSessionId()
  loading.value = false
  streamingMsg.value = null
  attachmentList.value = []
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

watch(
  () => route.name,
  (name) => {
    if (name === 'workspace') resetConversationState()
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
      placeholder: row.placeholder || '',
      emoji: ui.emoji,
      panel: ui.panel,
    }
  })
})

const scenarioTemplates = computed(() => {
  const raw = tm('home.templates')
  if (!Array.isArray(raw)) return []
  const labelById = Object.fromEntries(shortcutItems.value.map((item) => [item.id, item.label]))
  return raw.map((row) => ({
    ...row,
    label: labelById[row.id] || row.title,
  }))
})

const activeShortcutId = ref('')
const activeShortcut = computed(
  () => shortcutItems.value.find((it) => it.id === activeShortcutId.value) || null,
)
const activeScenarioTemplate = computed(
  () => scenarioTemplates.value.find((it) => it.id === activeShortcutId.value) || null,
)
const activeShortcutPill = computed(() => {
  const it = activeShortcut.value
  if (!it) return null
  return {
    label: it.label,
    emoji: it.emoji,
    pillClass: PILL_BY_ID[it.id] || '',
  }
})

const quotaItems = computed(() => {
  const usage = planSummary.value?.usage || {}
  const limits = planSummary.value?.limits || {}
  return [
    { label: t('home.quota.messages'), value: `${usage.messages ?? 0}/${limits.messages ?? 0}` },
    { label: t('home.quota.tokens'), value: `${usage.tokens ?? 0}/${limits.tokens ?? 0}` },
    { label: t('home.quota.attachments'), value: `${usage.attachments ?? 0}/${limits.attachments ?? 0}` },
  ]
})

function syncTheme() {
  dark.value = isDarkFn()
}

onMounted(() => {
  syncTheme()
  window.addEventListener('icore-theme-change', syncTheme)
  hydrateRecentSessions()
  loadPlanSummary()
  loadProjects()
  hydrateCurrentSession()
})

onUnmounted(() => {
  window.removeEventListener('icore-theme-change', syncTheme)
})

watch(
  () => route.params.sessionId,
  async (nextSessionId) => {
    const resolved = typeof nextSessionId === 'string' ? nextSessionId : newSessionId()
    if (resolved === sessionId.value) return
    messages.value = []
    sessionId.value = resolved
    loading.value = false
    streamingMsg.value = null
    attachmentList.value = []
    uploadError.value = ''
    activeShortcutId.value = ''
    await hydrateCurrentSession()
    await nextTick()
    if (scrollEl.value) scrollEl.value.scrollTop = 0
  },
)

async function scrollBottom() {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

// 前端 shortcut id → 后端 agent_hint 映射。docs 按钮走 knowledge_agent。
const SHORTCUT_HINT = {
  research: 'research',
  code: 'code',
  docs: 'knowledge',
  chat: 'chat',
  image: 'image',
  data: 'data',
}

function hydrateRecentSessions() {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_SESSIONS_KEY) || '[]')
    recentSessions.value = Array.isArray(raw) ? raw : []
  } catch {
    recentSessions.value = []
  }
}

async function loadProjects() {
  try {
    const payload = await fetchProjects()
    projectRecords.value = payload.projects || []
    if (Array.isArray(payload.recent_sessions) && payload.recent_sessions.length) {
      recentSessions.value = payload.recent_sessions.map((item) => ({
        sessionId: item.session_id,
        title: item.title,
        subtitle: item.subtitle,
        scenarioId: item.scenario_id || '',
        projectId: item.project_id,
        projectTitle: item.project_title,
        attachmentCount: item.attachment_count || 0,
        updatedAt: item.updated_at,
      }))
      localStorage.setItem(RECENT_SESSIONS_KEY, JSON.stringify(recentSessions.value))
    }
  } catch {
    projectRecords.value = []
  }
}

function saveRecentSession(meta = {}) {
  const template = activeScenarioTemplate.value
  const title = meta.title || template?.title || t('home.heroTitle')
  const subtitle = meta.subtitle || template?.description || t('home.subtitle')
  const current = recentSessions.value.filter((item) => item.sessionId !== sessionId.value)
  recentSessions.value = [
    {
      sessionId: sessionId.value,
      title,
      subtitle,
      scenarioId: template?.id || meta.scenarioId || '',
      projectId: meta.projectId || template?.id || 'general',
      projectTitle: meta.projectTitle || template?.title || t('home.heroTitle'),
      attachmentCount: Number(meta.attachmentCount ?? attachmentList.value.length ?? 0),
      updatedAt: Date.now(),
    },
    ...current,
  ].slice(0, 8)
  localStorage.setItem(RECENT_SESSIONS_KEY, JSON.stringify(recentSessions.value))
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

async function loadPlanSummary() {
  try {
    planSummary.value = await fetchPlan()
  } catch {
    planSummary.value = null
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
    messages.value = (state.messages || []).map((msg, index) => ({
      id: `${sessionId.value}-${index}-${msg.role}`,
      role: msg.role,
      content: msg.content || '',
      steps: [],
      stepsCollapsed: true,
      streaming: false,
    }))
    attachmentList.value = state.attachments || []
    if (!activeShortcutId.value) {
      const recent = recentSessions.value.find((item) => item.sessionId === sessionId.value)
      const matched = scenarioTemplates.value.find((item) => item.title === recent?.title)
      activeShortcutId.value = matched?.id || ''
    }
    saveRecentSession({
      title: recentSessions.value.find((item) => item.sessionId === sessionId.value)?.title || t('home.heroTitle'),
      subtitle: state.summary || recentSessions.value.find((item) => item.sessionId === sessionId.value)?.subtitle || t('home.subtitle'),
      attachmentCount: (state.attachments || []).length,
    })
    await syncCurrentProject({
      title: recentSessions.value.find((item) => item.sessionId === sessionId.value)?.title || t('home.heroTitle'),
      subtitle: state.summary || recentSessions.value.find((item) => item.sessionId === sessionId.value)?.subtitle || t('home.subtitle'),
      attachmentCount: (state.attachments || []).length,
    })
  } catch {
    await refreshAttachments()
  }
}

function composeScenarioPrompt(message) {
  const template = activeScenarioTemplate.value
  if (!template) return message
  const outputSections = (template.outputs || []).map((item) => `- ${item}`).join('\n')
  const markdownSections = (template.sections || [])
    .map((item) => `## ${item}\n- Keep this section concise and actionable.`)
    .join('\n\n')
  return [
    message,
    '',
    '---',
    'Please answer in markdown using this exact section order when it fits the task:',
    markdownSections,
    '',
    'Checklist:',
    outputSections,
  ].join('\n')
}

async function sendUserMessage(msg, agentHint = '', { skipUserBubble = false } = {}) {
  const text = String(msg ?? '').trim()
  if (!text || loading.value) return
  const requestText = composeScenarioPrompt(text)

  if (!skipUserBubble) {
    messages.value.push({ id: `${Date.now()}-u`, role: 'user', content: text })
    ensureChatRoute()
  }
  loading.value = true
  await scrollBottom()

  const assistant = {
    id: `${Date.now()}-a`,
    role: 'assistant',
    content: '',
    streaming: true,
    steps: [],
    stepsCollapsed: false,
  }
  messages.value.push(assistant)
  const replyIndex = messages.value.length - 1
  streamingMsg.value = messages.value[replyIndex]

  const ac = new AbortController()
  streamAbortController.value = ac

  function commitAssistant(partial) {
    const cur = messages.value[replyIndex]
    const next = { ...cur, ...partial }
    messages.value[replyIndex] = next
    streamingMsg.value = next
  }

  try {
    for await (const evt of chatStream(requestText, sessionId.value, agentHint, {
      signal: ac.signal,
    })) {
      if (!evt) continue
      if (evt.kind === 'token') {
        const cur = messages.value[replyIndex]
        commitAssistant({
          content: (cur.content || '') + (evt.text || ''),
        })
      } else if (evt.kind === 'status') {
        const cur = messages.value[replyIndex]
        commitAssistant({
          steps: [
            ...cur.steps,
            {
              step: evt.step,
              tool: evt.tool,
              input_preview: evt.input_preview,
            },
          ],
        })
      }
      await scrollBottom()
    }
  } catch (e) {
    const aborted = typeof e?.name === 'string' && e.name === 'AbortError'
    if (!aborted) {
      const errorMsg = String(e?.message || '')
      if (errorMsg.includes('401')) {
        signOut()
        router.push({ name: 'auth' })
      } else if (errorMsg.includes('402') || errorMsg.toLowerCase().includes('quota exceeded')) {
        // 额度超限：跳转到账户页面查看配额
        router.push({ name: 'account' })
      } else {
        commitAssistant({
          content: t('chat.requestFailed', { msg: errorMsg }),
        })
      }
    }
  } finally {
    streamAbortController.value = null
    commitAssistant({
      streaming: false,
      stepsCollapsed: true,
    })
    streamingMsg.value = null
    loading.value = false
    await loadPlanSummary()
    saveRecentSession({
      title: activeScenarioTemplate.value?.title || text.slice(0, 36),
      subtitle: text.slice(0, 80),
    })
    await syncCurrentProject({
      title: activeScenarioTemplate.value?.title || text.slice(0, 36),
      subtitle: text.slice(0, 80),
      sessionTitle: activeScenarioTemplate.value?.title || text.slice(0, 36),
      sessionSubtitle: text.slice(0, 80),
    })
    await scrollBottom()
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
      const { ref: imageRef, filename: savedName } = await attachImage(imageFile, sessionId.value)
      const url = imageUrl(imageRef)
      if (url) uploadedImages.push({ content: url, filename: savedName || imageFile.name })
    }
    const uploadedDataMeta = []
    for (const df of datas) {
      const meta = await attachData(df, sessionId.value)
      uploadedDataMeta.push({ filename: meta.filename || df.name })
    }
    await refreshAttachments()

    const hasImages = uploadedImages.length > 0
    const hasData = uploadedDataMeta.length > 0
    if (!hasImages && !hasData) return

    const caption = text || undefined
    if (hasImages && !hasData) {
      messages.value.push({
        id: `${Date.now()}-u`,
        role: 'user',
        type: 'image',
        images: uploadedImages,
        ...(caption ? { caption } : {}),
      })
    } else if (!hasImages && hasData) {
      messages.value.push({
        id: `${Date.now()}-u`,
        role: 'user',
        type: 'data',
        dataAttachments: uploadedDataMeta,
        ...(caption ? { caption } : {}),
      })
    } else {
      messages.value.push({
        id: `${Date.now()}-u`,
        role: 'user',
        type: 'composite',
        images: uploadedImages,
        dataAttachments: uploadedDataMeta,
        ...(caption ? { caption } : {}),
      })
    }
    await scrollBottom()
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
    await sendUserMessage(apiText, hint, { skipUserBubble: true })
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

function openRecentSession(targetSessionId) {
  router.push({ name: 'workspace-session', params: { sessionId: targetSessionId } })
}

function onSidebarNew() {
  messages.value = []
  const nextSessionId = newSessionId()
  sessionId.value = nextSessionId
  loading.value = false
  streamingMsg.value = null
  attachmentList.value = []
  uploadError.value = ''
  activeShortcutId.value = ''
  router.push({ name: 'workspace-session', params: { sessionId: nextSessionId } })
  saveRecentSession({
    title: activeScenarioTemplate.value?.title || t('home.heroTitle'),
    subtitle: t('home.subtitle'),
  })
  syncCurrentProject({
    title: activeScenarioTemplate.value?.title || t('home.heroTitle'),
    subtitle: t('home.subtitle'),
  })
  nextTick(() => {
    ;(messages.value.length ? searchRefChat.value : searchRefHome.value)?.focus?.()
    if (scrollEl.value) scrollEl.value.scrollTop = 0
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
