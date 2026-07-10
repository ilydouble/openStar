import { createApp } from 'vue'
import App from './App.vue'
import { getAccessToken } from './features/auth/application/session'
import i18n from './shared/i18n'
import { createAppRouter } from './router'
import { configureApiClient } from './shared/api/api-client'
import { initTheme } from './shared/theme/theme'
import './style.css'

initTheme()
configureApiClient({ tokenReader: getAccessToken })

const router = createAppRouter()

createApp(App).use(router).use(i18n).mount('#app')
