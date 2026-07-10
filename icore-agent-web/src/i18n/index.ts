import { createI18n } from 'vue-i18n'
import zhCN from '../locales/zh-CN.js'
import enUS from '../locales/en-US.js'
import { getLocalePreference } from '../stores/preferences'

type MessageSchema = typeof zhCN

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS,
} satisfies Record<string, MessageSchema>

const i18n = createI18n({
  legacy: false,
  locale: getLocalePreference(),
  fallbackLocale: 'en-US',
  messages,
})

export default i18n
