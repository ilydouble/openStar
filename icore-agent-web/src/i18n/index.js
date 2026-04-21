import { createI18n } from 'vue-i18n'
import zhCN from '../locales/zh-CN.js'
import enUS from '../locales/en-US.js'

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS,
}

const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem('locale') || 'zh-CN',
  fallbackLocale: 'en-US',
  messages,
})

export default i18n
