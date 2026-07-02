import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from './auth/session.js'

export const routes = [
  { path: '/', name: 'landing', component: () => import('./views/LandingView.vue') },
  { path: '/auth', name: 'auth', component: () => import('./views/AuthView.vue') },
  { path: '/enterprise', name: 'enterprise', component: () => import('./views/EnterpriseView.vue') },
  {
    path: '/account',
    name: 'account',
    component: () => import('./views/AccountView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/commerce',
    name: 'commerce',
    component: () => import('./views/CommerceDashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/app',
    name: 'workspace',
    component: () => import('./views/HomeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/app/:sessionId',
    name: 'workspace-session',
    component: () => import('./views/HomeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/chat/:sessionId?',
    redirect: (to) => ({
      name: to.params.sessionId ? 'workspace-session' : 'workspace',
      params: to.params.sessionId ? { sessionId: to.params.sessionId } : {},
    }),
  },
]

export function createAppRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes,
    scrollBehavior(to, _from, savedPosition) {
      if (to.hash) {
        return { el: to.hash, behavior: 'smooth' }
      }
      if (savedPosition) {
        return savedPosition
      }
      return { top: 0 }
    },
  })
  router.beforeEach((to) => {
    if (to.meta?.requiresAuth && !isAuthenticated()) {
      return {
        name: 'auth',
        query: { redirect: to.fullPath },
      }
    }
    if (to.name === 'auth' && isAuthenticated()) {
      return { name: 'workspace' }
    }
    return true
  })
  return router
}
