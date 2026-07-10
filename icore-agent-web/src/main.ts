import { createApp } from 'vue'
import App from './App.vue'
import i18n from './shared/i18n'
import { createAppRouter } from './router'
import { initTheme } from './shared/theme/theme'
import './style.css'

initTheme()

const router = createAppRouter()

createApp(App).use(router).use(i18n).mount('#app')
