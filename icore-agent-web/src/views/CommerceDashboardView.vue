<template>
  <CommerceShell
    :title="t('commerce.dashboard.title')"
    :subtitle="t('commerce.dashboard.subtitle')"
    :busy="diagnosisLoading"
    :status-text="diagnosisStatus"
    :error-text="diagnosisError"
    @sample="handleSampleDiagnosis"
    @uploaded="handleCsvUploaded"
  >
    <section class="grid gap-4 md:grid-cols-2 2xl:grid-cols-4" :aria-label="t('commerce.dashboard.metricsLabel')">
      <article
        v-for="metric in metrics"
        :key="metric.label"
        class="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.04]"
      >
        <p class="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{{ metric.label }}</p>
        <div class="mt-3 flex items-end justify-between gap-4">
          <p class="text-2xl font-semibold tabular-nums tracking-tight text-zinc-950 dark:text-white">{{ metric.value }}</p>
          <span :class="metric.badgeClass" class="rounded-lg px-2 py-1 text-xs font-semibold">{{ metric.badge }}</span>
        </div>
        <p class="mt-3 text-sm leading-6 text-zinc-500 dark:text-zinc-400">{{ metric.body }}</p>
      </article>
    </section>

    <section class="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
      <article class="rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
        <div class="border-b border-zinc-200 px-5 py-4 dark:border-white/10">
          <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ t('commerce.dashboard.skuQueueTitle') }}</p>
          <p class="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{{ t('commerce.dashboard.skuQueueSubtitle') }}</p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:bg-white/[0.03] dark:text-zinc-400">
              <tr>
                <th class="px-5 py-3 font-semibold">{{ t('commerce.dashboard.table.sku') }}</th>
                <th class="px-5 py-3 font-semibold">{{ t('commerce.dashboard.table.risk') }}</th>
                <th class="px-5 py-3 font-semibold">{{ t('commerce.dashboard.table.daysLeft') }}</th>
                <th class="px-5 py-3 font-semibold">{{ t('commerce.dashboard.table.action') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-zinc-200 dark:divide-white/10">
              <tr v-for="item in skuRisks" :key="item.sku">
                <td class="px-5 py-4 font-semibold text-zinc-950 dark:text-white">{{ item.sku }}</td>
                <td class="px-5 py-4 text-zinc-600 dark:text-zinc-300">{{ item.risk }}</td>
                <td class="px-5 py-4 tabular-nums text-zinc-600 dark:text-zinc-300">{{ item.daysLeft }}</td>
                <td class="px-5 py-4 text-zinc-600 dark:text-zinc-300">{{ item.action }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.04]">
        <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ t('commerce.dashboard.reportTitle') }}</p>
        <p class="mt-2 text-sm leading-6 text-zinc-500 dark:text-zinc-400">
          {{ reportBody }}
        </p>
        <div class="mt-5 space-y-3">
          <div
            v-for="task in tasks"
            :key="task.title"
            class="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-white/10 dark:bg-zinc-950"
          >
            <div class="flex items-start justify-between gap-4">
              <p class="text-sm font-semibold text-zinc-950 dark:text-white">{{ task.title }}</p>
              <span class="rounded-lg bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-300/15 dark:text-amber-200">{{ task.status }}</span>
            </div>
            <p class="mt-2 text-xs leading-5 text-zinc-500 dark:text-zinc-400">{{ task.body }}</p>
          </div>
        </div>
      </article>
    </section>
  </CommerceShell>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  createCommerceDiagnosis,
  createSampleCommerceDiagnosis,
  uploadFileAsset,
} from '../api/agent.js'
import CommerceShell from '../components/commerce/CommerceShell.vue'

const { t, tm, locale } = useI18n()

const diagnosisReport = ref(null)
const diagnosisLoading = ref(false)
const diagnosisError = ref('')
const diagnosisSource = ref('')

const metricBadgeClasses = [
  'bg-emerald-100 text-emerald-800 dark:bg-emerald-300/15 dark:text-emerald-200',
  'bg-sky-100 text-sky-800 dark:bg-sky-300/15 dark:text-sky-200',
  'bg-rose-100 text-rose-800 dark:bg-rose-300/15 dark:text-rose-200',
  'bg-amber-100 text-amber-800 dark:bg-amber-300/15 dark:text-amber-200',
]

function localizedArray(path) {
  const value = tm(path)
  return Array.isArray(value) ? value : []
}

const metrics = computed(() =>
  (diagnosisReport.value ? diagnosisMetrics.value : localizedArray('commerce.dashboard.metrics')).map((metric, index) => ({
    ...metric,
    badgeClass: metricBadgeClasses[index] || metricBadgeClasses[0],
  })),
)
const skuRisks = computed(() => diagnosisReport.value ? diagnosisRisks.value : localizedArray('commerce.dashboard.skuRisks'))
const tasks = computed(() => diagnosisReport.value ? diagnosisTasks.value : localizedArray('commerce.dashboard.tasks'))
const reportBody = computed(() => diagnosisReport.value?.report_summary || t('commerce.dashboard.reportBody'))
const diagnosisStatus = computed(() => {
  if (diagnosisLoading.value) return t('commerce.dashboard.status.running')
  if (diagnosisReport.value) {
    return t('commerce.dashboard.status.ready', {
      file: diagnosisSource.value || diagnosisReport.value.source_file?.filename || '',
    })
  }
  return ''
})

const diagnosisMetrics = computed(() => {
  const metricsValue = diagnosisReport.value?.metrics || {}
  return [
    {
      label: t('commerce.dashboard.liveMetrics.skus'),
      value: String(metricsValue.sku_count ?? 0),
      badge: t('commerce.dashboard.liveMetrics.fromCsv'),
      body: t('commerce.dashboard.liveMetrics.skusBody'),
    },
    {
      label: t('commerce.dashboard.liveMetrics.revenue'),
      value: formatMoney(metricsValue.total_revenue),
      badge: t('commerce.dashboard.liveMetrics.calculated'),
      body: t('commerce.dashboard.liveMetrics.revenueBody'),
    },
    {
      label: t('commerce.dashboard.liveMetrics.margin'),
      value: formatPercent(metricsValue.gross_margin_rate),
      badge: t('commerce.dashboard.liveMetrics.calculated'),
      body: t('commerce.dashboard.liveMetrics.marginBody'),
    },
    {
      label: t('commerce.dashboard.liveMetrics.tasks'),
      value: String(diagnosisReport.value?.tasks?.length ?? 0),
      badge: t('commerce.dashboard.liveMetrics.generated'),
      body: t('commerce.dashboard.liveMetrics.tasksBody'),
    },
  ]
})

const diagnosisRisks = computed(() =>
  (diagnosisReport.value?.risks || []).map((risk) => ({
    sku: risk.sku || '-',
    risk: risk.message || risk.type || '-',
    daysLeft: risk.days_left != null ? t('commerce.dashboard.daysValue', { days: risk.days_left }) : '-',
    action: risk.type === 'stockout'
      ? t('commerce.dashboard.actions.replenish')
      : t('commerce.dashboard.actions.review'),
  })),
)

const diagnosisTasks = computed(() =>
  (diagnosisReport.value?.tasks || []).map((task) => ({
    title: task.title || task.type || '-',
    status: task.priority === 'high'
      ? t('commerce.dashboard.taskStatus.high')
      : t('commerce.dashboard.taskStatus.suggested'),
    body: task.body || '',
  })),
)

async function handleCsvUploaded(file) {
  await runDiagnosis(file)
}

async function handleSampleDiagnosis() {
  await runSampleDiagnosis()
}

async function runDiagnosis(file) {
  diagnosisLoading.value = true
  diagnosisError.value = ''
  try {
    const uploaded = await uploadFileAsset(file)
    const report = await createCommerceDiagnosis(uploaded.file_uuid, {
      locale: locale.value,
    })
    diagnosisReport.value = report
    diagnosisSource.value = uploaded.original_filename || uploaded.filename || file.name
  } catch (err) {
    diagnosisError.value = err?.message || t('commerce.dashboard.status.failed')
  } finally {
    diagnosisLoading.value = false
  }
}

async function runSampleDiagnosis() {
  diagnosisLoading.value = true
  diagnosisError.value = ''
  try {
    const report = await createSampleCommerceDiagnosis({
      locale: locale.value,
    })
    diagnosisReport.value = report
    diagnosisSource.value = report.source_file?.filename || 'commerce-sample.csv'
  } catch (err) {
    diagnosisError.value = err?.message || t('commerce.dashboard.status.failed')
  } finally {
    diagnosisLoading.value = false
  }
}

function formatMoney(value) {
  const number = Number(value || 0)
  return new Intl.NumberFormat(locale.value === 'zh-CN' ? 'zh-CN' : 'en-US', {
    maximumFractionDigits: 0,
  }).format(number)
}

function formatPercent(value) {
  const number = Number(value || 0)
  return `${Math.round(number * 1000) / 10}%`
}

</script>
