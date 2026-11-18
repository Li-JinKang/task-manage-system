import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录 - TaskHub', requiresAuth: false },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '我的工作台', requiresAuth: true, breadcrumb: '首页' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
