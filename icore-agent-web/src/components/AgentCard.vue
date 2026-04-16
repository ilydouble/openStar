<template>
  <!-- 大卡片：对应图中 CORE APPLICATIONS 区域 -->
  <div
    class="bg-white rounded-2xl border border-black/8 p-5 flex flex-col gap-3 hover:shadow-md transition cursor-pointer group"
    @click="$emit('open', agent)"
  >
    <!-- 顶部：图标 + 徽章 -->
    <div class="flex items-start justify-between">
      <div :class="agent.iconBg" class="w-11 h-11 rounded-xl flex items-center justify-center text-white text-xl shrink-0">
        {{ agent.icon }}
      </div>
      <span v-if="agent.badge"
        :class="agent.badge === '精选' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'"
        class="text-[11px] font-semibold px-2 py-0.5 rounded-full"
      >
        {{ agent.badge }}
      </span>
    </div>

    <!-- 名称 + 分类 -->
    <div>
      <p class="font-semibold text-gray-900 text-sm">{{ agent.name }}</p>
      <p class="text-xs text-gray-400 mt-0.5">{{ agent.category }}</p>
    </div>

    <!-- 描述 -->
    <p class="text-xs text-gray-500 leading-relaxed line-clamp-3 flex-1">
      {{ agent.description }}
    </p>

    <!-- 打开链接 -->
    <div class="flex items-center gap-1 text-xs font-medium text-gray-700 group-hover:text-gray-900 transition">
      打开
      <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" d="M5 12h14M12 5l7 7-7 7"/>
      </svg>
    </div>
  </div>
</template>

<script setup>
defineProps({ agent: Object })
defineEmits(['open'])
</script>
