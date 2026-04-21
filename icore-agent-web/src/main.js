import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HomeView from './views/HomeView.vue'
import i18n from './i18n'
import { initTheme } from './theme'
import './style.css'

initTheme()

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/chat/:sessionId?', redirect: '/' },
  ],
})

createApp(App).use(router).use(i18n).mount('#app')
