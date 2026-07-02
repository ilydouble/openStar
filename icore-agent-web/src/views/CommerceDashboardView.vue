<template>
  <CommerceShell
    title="AI Operations Diagnosis"
    subtitle="V1 starts with sample CSVs: products, orders, inventory, and suppliers. The output is a report, SKU risks, and today&apos;s tasks."
  >
    <section class="grid gap-4 md:grid-cols-2 2xl:grid-cols-4" aria-label="Commerce metrics">
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
          <p class="text-sm font-semibold text-zinc-950 dark:text-white">SKU risk queue</p>
          <p class="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Sample CSV data shows what the first diagnosis will surface after upload.</p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:bg-white/[0.03] dark:text-zinc-400">
              <tr>
                <th class="px-5 py-3 font-semibold">SKU</th>
                <th class="px-5 py-3 font-semibold">Risk</th>
                <th class="px-5 py-3 font-semibold">Days left</th>
                <th class="px-5 py-3 font-semibold">Action</th>
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
        <p class="text-sm font-semibold text-zinc-950 dark:text-white">AI diagnosis report</p>
        <p class="mt-2 text-sm leading-6 text-zinc-500 dark:text-zinc-400">
          The uploaded sample sheets are enough to flag two stockout risks, one margin review, and one supplier follow-up. This report is the first conversion hook for prospects.
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
import CommerceShell from '../components/commerce/CommerceShell.vue'

const metrics = [
  { label: 'CSV templates', value: '4', badge: 'Required', badgeClass: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-300/15 dark:text-emerald-200', body: 'Products, orders, inventory, and suppliers are enough for the first diagnosis.' },
  { label: 'Diagnosis score', value: '72', badge: 'Review', badgeClass: 'bg-sky-100 text-sky-800 dark:bg-sky-300/15 dark:text-sky-200', body: 'A simple sample score summarizing margin, stock, and supplier risk.' },
  { label: 'SKU risks', value: '6', badge: '2 urgent', badgeClass: 'bg-rose-100 text-rose-800 dark:bg-rose-300/15 dark:text-rose-200', body: 'Risks discovered from uploaded inventory and order history.' },
  { label: 'Today tasks', value: '9', badge: 'Generated', badgeClass: 'bg-amber-100 text-amber-800 dark:bg-amber-300/15 dark:text-amber-200', body: 'Suggested actions created from the diagnosis report.' },
]

const skuRisks = [
  { sku: 'TRVL-CABLE-3P', risk: 'Fast seller, low stock', daysLeft: '9 days', action: 'Ask supplier for 500 units' },
  { sku: 'DESK-LAMP-MINI', risk: 'Margin dropped', daysLeft: '18 days', action: 'Review freight cost' },
  { sku: 'PACK-CUBE-SET', risk: 'Supplier lead-time risk', daysLeft: '13 days', action: 'Confirm production slot' },
  { sku: 'USB-HUB-6IN1', risk: 'Refund rate rising', daysLeft: '22 days', action: 'Check support tickets' },
]

const tasks = [
  { title: 'Replenish TRVL-CABLE-3P', status: 'Suggested', body: 'Current sell-through suggests stockout before the next supplier lead-time window closes.' },
  { title: 'Send supplier follow-up', status: 'Draft', body: 'Ask Shenzhen Brightline to confirm MOQ, updated quote, and earliest ship date.' },
  { title: 'Review low-margin desk lamp', status: 'Suggested', body: 'Recent freight allocation moved estimated gross margin below the pilot threshold.' },
]
</script>
