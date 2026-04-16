import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HomeView from './views/HomeView.vue'
import ChatView from './views/ChatView.vue'
import i18n from './i18n'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/chat/:sessionId?', component: ChatView },
  ],
})

createApp(App).use(router).use(i18n).mount('#app')
