<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        @click.self="handleSkip"
      >
        <div
          class="relative flex max-h-[min(92dvh,calc(100dvh-2rem))] w-full max-w-3xl flex-col overflow-hidden rounded-[2rem] border border-zinc-200/80 bg-white shadow-2xl dark:border-white/10 dark:bg-zinc-900"
          @click.stop
        >
          <button
            type="button"
            class="absolute right-6 top-6 rounded-full p-2 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-950 dark:hover:bg-white/10 dark:hover:text-white"
            @click="handleSkip"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <div class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-6 sm:p-12">
            <div class="text-center">
              <p class="inline-flex rounded-full border border-violet-200 bg-violet-50/90 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-violet-700 shadow-sm dark:border-violet-300/20 dark:bg-violet-300/10 dark:text-violet-200">
                {{ t('onboarding.eyebrow') }}
              </p>
              <h2 class="mt-4 text-3xl font-semibold tracking-[-0.04em] text-zinc-950 dark:text-white sm:text-4xl">
                {{ t('onboarding.title') }}
              </h2>
              <p class="mx-auto mt-4 max-w-xl text-base leading-7 text-zinc-600 dark:text-zinc-300">
                {{ t('onboarding.subtitle') }}
              </p>
            </div>

            <div class="mt-8 grid gap-4 sm:grid-cols-2">
              <button
                v-for="(scenario, index) in scenarios"
                :key="index"
                type="button"
                class="group rounded-2xl border border-zinc-200/80 bg-white p-6 text-left transition-all duration-200 hover:scale-[1.02] hover:border-violet-300 hover:shadow-lg dark:border-white/10 dark:bg-white/[0.04] dark:hover:border-violet-400/50"
                @click="handleSelectScenario(scenario.agentHint)"
              >
                <div class="flex items-start gap-4">
                  <div
                    class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl transition-transform group-hover:scale-110"
                    :class="scenario.bgClass"
                  >
                    {{ scenario.emoji }}
                  </div>
                  <div class="flex-1">
                    <h3 class="text-lg font-semibold text-zinc-950 dark:text-white">
                      {{ scenario.title }}
                    </h3>
                    <p class="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
                      {{ scenario.body }}
                    </p>
                  </div>
                </div>
              </button>
            </div>

            <div class="mt-8 flex items-center justify-between gap-4">
              <button
                type="button"
                class="text-sm font-medium text-zinc-500 transition hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-white"
                @click="handleSkip"
              >
                {{ t('onboarding.skip') }}
              </button>
              <button
                type="button"
                class="rounded-full bg-zinc-950 px-6 py-2.5 text-sm font-semibold text-white transition hover:scale-[1.02] dark:bg-white dark:text-zinc-950"
                @click="handleSkip"
              >
                {{ t('onboarding.explore') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, tm } = useI18n()

defineProps({
  show: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['select-scenario', 'close'])

const scenarios = computed(() => {
  const raw = tm('onboarding.scenarios')
  return Array.isArray(raw) ? raw : []
})

function handleSelectScenario(agentHint) {
  emit('select-scenario', agentHint)
  emit('close')
}

function handleSkip() {
  emit('close')
}
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active > div,
.modal-leave-active > div {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.modal-enter-from > div,
.modal-leave-to > div {
  transform: scale(0.95);
  opacity: 0;
}
</style>
