import { createApp } from 'vue'
import App from './App.vue'
import i18n from './i18n'
import { createAppRouter } from './router'
import { initTheme } from './theme'
import './style.css'

initTheme()

const router = createAppRouter()

createApp(App).use(router).use(i18n).mount('#app')
