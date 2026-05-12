<template>
  <aside
    class="flex h-full w-[4.5rem] shrink-0 flex-col border-r border-zinc-200/80 bg-white/90 backdrop-blur-xl transition-colors duration-300 ease-out dark:border-white/[0.08] dark:bg-zinc-950/50 sm:w-[13.5rem]"
  >
    <div class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-2 pt-4 sm:px-3">
      <button
        type="button"
        @click="$emit('new')"
        class="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm font-medium text-zinc-700 transition-colors duration-200 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-white"
      >
        <span
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-200/90 bg-zinc-50 text-zinc-600 transition-colors duration-200 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-400"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M12 5v14M5 12h14" />
          </svg>
        </span>
        <span class="hidden truncate sm:inline">{{ t('home.sidebar.new') }}</span>
      </button>

      <RouterLink to="/app" custom v-slot="{ href, navigate, isExactActive }">
        <a
          :href="href"
          @click="navigate"
          :class="navItemClass(isExactActive && !hasChatMessages)"
        >
          <span :class="iconWrapClass(isExactActive && !hasChatMessages)">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-5v-6H10v6H5a1 1 0 01-1-1v-9.5z"
              />
            </svg>
          </span>
          <span class="hidden truncate sm:inline">{{ t('home.sidebar.home') }}</span>
        </a>
      </RouterLink>

      <RouterLink to="/app" custom v-slot="{ href, navigate }">
        <a :href="href" @click="navigate" :class="navItemClass(hasChatMessages)">
          <span :class="iconWrapClass(hasChatMessages)">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M8 10h.01M12 10h.01M16 10h.01M4 18l4-4h10a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12z"
              />
            </svg>
          </span>
          <span class="hidden truncate sm:inline">{{ t('home.sidebar.chat') }}</span>
        </a>
      </RouterLink>

      <RouterLink to="/account" custom v-slot="{ href, navigate, isActive }">
        <a :href="href" @click="navigate" :class="navItemClass(isActive)">
          <span :class="iconWrapClass(isActive)">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6.75a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.5 19.5a7.5 7.5 0 0115 0" />
            </svg>
          </span>
          <span class="hidden truncate sm:inline">{{ t('home.signIn') }}</span>
        </a>
      </RouterLink>

      <div class="mt-3 hidden sm:block">
        <p class="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
          {{ t('home.recent.title') }}
        </p>
        <div v-if="recentSessions.length" class="mt-2 space-y-1.5">
          <RouterLink
            v-for="item in recentSessions"
            :key="item.sessionId"
            :to="{ name: 'workspace-session', params: { sessionId: item.sessionId } }"
            class="block rounded-xl border border-zinc-200/80 bg-zinc-50/80 px-3 py-2 transition hover:border-zinc-300 hover:bg-white dark:border-white/[0.08] dark:bg-white/[0.03] dark:hover:border-white/12 dark:hover:bg-white/[0.06]"
          >
            <p class="truncate text-xs font-semibold text-zinc-700 dark:text-zinc-200">
              {{ item.title }}
            </p>
            <p class="mt-1 truncate text-[11px] text-zinc-500 dark:text-zinc-400">
              {{ item.subtitle }}
            </p>
          </RouterLink>
        </div>
        <p v-else class="mt-2 px-2 text-xs text-zinc-400 dark:text-zinc-500">
          {{ t('home.recent.empty') }}
        </p>
      </div>

      <div class="mt-4 hidden sm:block">
        <p class="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
          {{ t('home.projects.title') }}
        </p>
        <div v-if="recentProjects.length" class="mt-2 space-y-1.5">
          <div
            v-for="project in recentProjects"
            :key="project.id"
            class="rounded-xl border border-zinc-200/80 bg-zinc-50/80 px-3 py-2 dark:border-white/[0.08] dark:bg-white/[0.03]"
          >
            <p class="truncate text-xs font-semibold text-zinc-700 dark:text-zinc-200">
              {{ project.title }}
            </p>
            <p class="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
              {{ project.sessions }} {{ t('home.projects.sessions') }} · {{ project.assets }} {{ t('home.projects.assets') }}
            </p>
          </div>
        </div>
        <p v-else class="mt-2 px-2 text-xs text-zinc-400 dark:text-zinc-500">
          {{ t('home.projects.empty') }}
        </p>
      </div>

      <button type="button" :class="navItemClass(false)" class="w-full cursor-default opacity-50">
        <span :class="iconWrapClass(false)">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </span>
        <span class="hidden truncate sm:inline">{{ t('home.sidebar.flow') }}</span>
      </button>

      <button type="button" :class="navItemClass(false)" class="w-full cursor-default opacity-50">
        <span :class="iconWrapClass(false)">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <circle cx="5" cy="12" r="1.5" fill="currentColor" />
            <circle cx="12" cy="12" r="1.5" fill="currentColor" />
            <circle cx="19" cy="12" r="1.5" fill="currentColor" />
          </svg>
        </span>
        <span class="hidden truncate sm:inline">{{ t('home.sidebar.more') }}</span>
      </button>
    </div>

    <SidebarFooterControls class="mt-auto shrink-0" />
  </aside>
</template>

<script setup>
import { inject, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import SidebarFooterControls from './SidebarFooterControls.vue'

const hasChatMessages = inject(
  'hasChatMessages',
  computed(() => false),
)

defineProps({
  recentSessions: {
    type: Array,
    default: () => [],
  },
  recentProjects: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['new'])

const { t } = useI18n()

function navItemClass(active) {
  return [
    'flex items-center gap-3 rounded-xl px-2 py-2 text-sm font-medium transition-colors duration-200',
    active
      ? 'bg-zinc-200/90 text-zinc-950 shadow-sm ring-1 ring-zinc-300/50 dark:bg-white/[0.1] dark:text-white dark:shadow-[0_0_0_1px_rgba(255,255,255,0.08)] dark:ring-white/10'
      : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-500 dark:hover:bg-white/[0.05] dark:hover:text-zinc-200',
  ]
}

function iconWrapClass(active) {
  return [
    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-colors duration-200',
    active
      ? 'border-zinc-300/90 bg-white text-zinc-950 dark:border-white/15 dark:bg-white/[0.1] dark:text-white'
      : 'border-zinc-200/90 bg-zinc-50 text-zinc-600 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-400',
  ]
}
</script>
