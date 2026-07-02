<template>
  <aside class="flex min-h-0 flex-col border-r border-zinc-200 bg-white text-zinc-900 dark:border-white/10 dark:bg-zinc-950 dark:text-zinc-100 lg:w-64">
    <div class="border-b border-zinc-200 px-5 py-5 dark:border-white/10">
      <RouterLink to="/commerce" class="block">
        <p class="text-sm font-semibold text-zinc-950 dark:text-white">iCore Commerce OS</p>
        <p class="mt-1 text-xs leading-5 text-zinc-500 dark:text-zinc-400">CSV diagnosis pilot</p>
      </RouterLink>
    </div>

    <nav class="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Commerce navigation">
      <RouterLink
        v-for="item in navItems"
        :key="item.label"
        :to="item.to"
        class="flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium text-zinc-600 transition hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-300 dark:hover:bg-white/10 dark:hover:text-white"
        :class="item.active ? 'bg-zinc-950 text-white hover:bg-zinc-950 hover:text-white dark:bg-white dark:text-zinc-950 dark:hover:bg-white' : ''"
      >
        <component :is="item.icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="border-t border-zinc-200 p-4 dark:border-white/10">
      <RouterLink
        to="/app"
        class="mb-3 flex min-h-10 items-center gap-3 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-600 transition hover:border-zinc-300 hover:text-zinc-950 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300 dark:hover:text-white"
      >
        <Bot class="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>AI Workspace</span>
      </RouterLink>
      <div class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-950 dark:border-amber-300/20 dark:bg-amber-300/10 dark:text-amber-100">
        <p class="text-xs font-semibold uppercase tracking-wide">Pilot mode</p>
        <p class="mt-2 text-xs leading-5">V1 focuses on one loop: upload CSV, generate diagnosis, review tasks.</p>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import {
  BarChart3,
  Bot,
  Boxes,
  ClipboardList,
  FileText,
  Headphones,
  PackageSearch,
  Ship,
  Truck,
  Upload,
} from 'lucide-vue-next'

const navItems = [
  { label: 'Diagnosis', icon: BarChart3, to: '/commerce', active: true },
  { label: 'Report', icon: FileText, to: '/commerce' },
  { label: 'Tasks', icon: ClipboardList, to: '/commerce' },
  { label: 'Products', icon: PackageSearch, to: '/commerce' },
  { label: 'Inventory', icon: Boxes, to: '/commerce' },
  { label: 'Suppliers', icon: Truck, to: '/commerce' },
  { label: 'Orders CSV', icon: Ship, to: '/commerce' },
  { label: 'Support later', icon: Headphones, to: '/commerce' },
  { label: 'CSV Import', icon: Upload, to: '/commerce' },
]
</script>
