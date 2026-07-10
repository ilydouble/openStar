import { createRouter, createWebHistory, type RouteRecordRaw, type Router } from 'vue-router'
import { authApplication, loadAuthPage } from './features/auth'
import { loadAccountPage } from './features/account'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'landing', component: () => import('./features/landing/interfaces/LandingView.vue') },
  { path: '/auth', name: 'auth', component: loadAuthPage },
  { path: '/enterprise', name: 'enterprise', component: () => import('./features/enterprise/interfaces/EnterpriseView.vue') },
  {
    path: '/account',
    name: 'account',
    component: loadAccountPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/app',
    name: 'workspace',
    component: () => import('./features/workspace/interfaces/HomeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/app/:sessionId',
    name: 'workspace-session',
    component: () => import('./features/workspace/interfaces/HomeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/chat/:sessionId?',
    redirect: (to) => ({
      name: to.params.sessionId ? 'workspace-session' : 'workspace',
      params: to.params.sessionId ? { sessionId: String(to.params.sessionId) } : {},
    }),
  },
]

/** Create the application router with auth guards and scroll restoration. */
export function createAppRouter(): Router {
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
    if (to.meta?.requiresAuth && !authApplication.isAuthenticated()) {
      return {
        name: 'auth',
        query: { redirect: to.fullPath },
      }
    }
    if (to.name === 'auth' && authApplication.isAuthenticated()) {
      return { name: 'workspace' }
    }
    return true
  })
  return router
}
