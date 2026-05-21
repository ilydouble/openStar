<template>
  <router-view />
</template>

<script setup>
import { watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale, t } = useI18n()

watchEffect(() => {
  document.documentElement.lang = locale.value === 'zh-CN' ? 'zh-CN' : 'en-US'
  document.title = t('app.documentTitle')
})
</script>
