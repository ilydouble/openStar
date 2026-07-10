import { createApp } from 'vue'
import App from './App.vue'
import { authApplication } from './features/auth'
import i18n from './shared/presentation/i18n'
import { createAppRouter } from './router'
import { configureApiClient } from './shared/infrastructure/http'
import { initTheme } from './shared/presentation/theme/theme'
import './style.css'

initTheme()
configureApiClient({ tokenReader: authApplication.getAccessToken })

const router = createAppRouter()

createApp(App).use(router).use(i18n).mount('#app')
