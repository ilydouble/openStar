<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        @click.self="close"
      >
        <div
          class="relative w-full max-w-2xl overflow-hidden rounded-[2rem] border border-zinc-200/80 bg-white shadow-2xl dark:border-white/10 dark:bg-zinc-950"
          @click.stop
        >
          <button
            type="button"
            class="absolute right-5 top-5 rounded-full p-2 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-950 dark:hover:bg-white/10 dark:hover:text-white"
            :aria-label="t('paymentSimulation.close')"
            @click="close"
          >
            <span aria-hidden="true">x</span>
          </button>

          <div class="grid gap-0 md:grid-cols-[0.92fr_1.08fr]">
            <div class="bg-zinc-950 p-6 text-white dark:bg-white dark:text-zinc-950 sm:p-8">
              <span class="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-semibold dark:bg-zinc-950/10">
                {{ t('paymentSimulation.badge') }}
              </span>
              <h2 class="mt-5 text-2xl font-semibold tracking-tight">{{ t('paymentSimulation.title') }}</h2>
              <p class="mt-3 text-sm leading-6 text-zinc-300 dark:text-zinc-700">
                {{ t('paymentSimulation.subtitle') }}
              </p>

              <div class="mt-8 rounded-2xl bg-white p-4 text-zinc-950 dark:bg-zinc-950 dark:text-white">
                <div class="grid aspect-square grid-cols-7 gap-1">
                  <span
                    v-for="(filled, index) in qrCells"
                    :key="index"
                    class="rounded-[3px]"
                    :class="filled ? 'bg-zinc-950 dark:bg-white' : 'bg-zinc-100 dark:bg-white/10'"
                  />
                </div>
              </div>
              <p class="mt-3 break-all text-xs text-zinc-400 dark:text-zinc-600">{{ checkout?.payUrl }}</p>
            </div>

            <div class="p-6 text-zinc-950 dark:text-white sm:p-8">
              <div v-if="isPaid">
                <p class="text-sm font-semibold text-emerald-600 dark:text-emerald-300">
                  {{ t('paymentSimulation.successEyebrow') }}
                </p>
                <h3 class="mt-3 text-2xl font-semibold">{{ t('paymentSimulation.successTitle') }}</h3>
                <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                  {{ t('paymentSimulation.successBody') }}
                </p>
                <button
                  type="button"
                  class="mt-8 inline-flex w-full items-center justify-center rounded-full bg-zinc-950 px-5 py-3 text-sm font-semibold text-white dark:bg-white dark:text-zinc-950"
                  @click="close"
                >
                  {{ t('paymentSimulation.continue') }}
                </button>
              </div>

              <div v-else>
                <p class="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
                  {{ t('paymentSimulation.orderTitle') }}
                </p>
                <h3 class="mt-3 text-2xl font-semibold">{{ planName }}</h3>
                <p class="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-300">{{ planDescription }}</p>

                <dl class="mt-6 space-y-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-4 text-sm dark:border-white/10 dark:bg-white/[0.04]">
                  <div class="flex items-center justify-between gap-4">
                    <dt class="text-zinc-500 dark:text-zinc-400">{{ t('paymentSimulation.amount') }}</dt>
                    <dd class="font-semibold">{{ amountLabel }}</dd>
                  </div>
                  <div class="flex items-center justify-between gap-4">
                    <dt class="text-zinc-500 dark:text-zinc-400">{{ t('paymentSimulation.orderNo') }}</dt>
                    <dd class="break-all text-right text-xs font-medium">{{ checkout?.orderNo }}</dd>
                  </div>
                  <div class="flex items-center justify-between gap-4">
                    <dt class="text-zinc-500 dark:text-zinc-400">{{ t('paymentSimulation.status') }}</dt>
                    <dd class="font-semibold text-amber-600 dark:text-amber-300">{{ t('paymentSimulation.pending') }}</dd>
                  </div>
                </dl>

                <div class="mt-6 space-y-3 text-sm text-zinc-600 dark:text-zinc-300">
                  <p>{{ t('paymentSimulation.stepScan') }}</p>
                  <p>{{ t('paymentSimulation.stepCallback') }}</p>
                </div>

                <button
                  type="button"
                  class="mt-8 inline-flex w-full items-center justify-center rounded-full bg-zinc-950 px-5 py-3 text-sm font-semibold text-white dark:bg-white dark:text-zinc-950"
                  @click="markPaid"
                >
                  {{ t('paymentSimulation.markPaid') }}
                </button>
                <button
                  type="button"
                  class="mt-3 inline-flex w-full items-center justify-center rounded-full border border-zinc-200 bg-white px-5 py-3 text-sm font-semibold text-zinc-700 dark:border-white/10 dark:bg-white/[0.04] dark:text-zinc-100"
                  @click="close"
                >
                  {{ t('paymentSimulation.cancel') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  completeSimulatedCheckout,
  createSimulatedCheckout,
  formatSimulatedAmount,
} from '../utils/simulatedCheckout.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  planKey: { type: String, default: 'pilot' },
})

const emit = defineEmits(['dismiss', 'paid'])

const { t } = useI18n()
const checkout = ref(null)

const isPaid = computed(() => checkout.value?.status === 'paid')
const amountLabel = computed(() => formatSimulatedAmount(checkout.value?.amountCents || 0, checkout.value?.currency))
const planName = computed(() => t(`paymentSimulation.plans.${checkout.value?.planKey || props.planKey}.name`))
const planDescription = computed(() => t(`paymentSimulation.plans.${checkout.value?.planKey || props.planKey}.description`))
const qrCells = computed(() => {
  const source = String(checkout.value?.orderNo || 'SIMULATED-PAYMENT')
  return Array.from({ length: 49 }, (_, index) => {
    const code = source.charCodeAt(index % source.length)
    return (code + index * 7) % 4 !== 0
  })
})

watch(
  () => [props.show, props.planKey],
  ([show]) => {
    if (show) {
      checkout.value = createSimulatedCheckout(props.planKey)
    }
  },
  { immediate: true },
)

/** Complete the simulated payment and notify the parent view. */
function markPaid() {
  checkout.value = completeSimulatedCheckout(checkout.value)
  emit('paid', checkout.value)
}

/** Close the simulated payment modal without changing the parent route. */
function close() {
  emit('dismiss')
}
</script>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
