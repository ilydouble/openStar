<template>
  <!-- 小卡片：对应图中 OTHER TOOLS 区域 -->
  <div
    class="bg-white rounded-xl border border-black/8 p-4 flex flex-col gap-2 hover:shadow-sm transition cursor-pointer group"
    @click="$emit('open', tool)"
  >
    <div :class="tool.iconBg" class="w-9 h-9 rounded-lg flex items-center justify-center text-white text-base shrink-0">
      {{ tool.icon }}
    </div>
    <div>
      <p class="font-medium text-gray-900 text-xs">{{ tool.name }}</p>
      <p class="text-[11px] text-gray-400 mt-0.5">{{ tool.category }}</p>
    </div>
    <p class="text-[11px] text-gray-500 leading-relaxed line-clamp-2">{{ tool.description }}</p>
  </div>
</template>

<script setup>
defineProps({ tool: Object })
defineEmits(['open'])
</script>
