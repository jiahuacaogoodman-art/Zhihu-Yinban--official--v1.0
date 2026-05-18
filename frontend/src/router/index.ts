import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

/**
 * Vue Router — Phase 6: history mode
 *
 * Phase 6 把 / 切到 v2:后端对 / 的所有非 /api、非 /static 请求都返回
 * static/v2/index.html(SPA catch-all)。所以可以从 hash 模式升级到 history 模式,
 * URL 更干净(/beds 而非 /#/beds)。
 *
 * 注意:后端 StaticFiles(html=True) 已经实现了 SPA fallback。
 */

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/Landing.vue'),
    meta: { title: '首页', guest: true, fullBleed: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', guest: true, fullBleed: true },
  },
  {
    path: '/beds',
    name: 'beds',
    component: () => import('../views/BedList.vue'),
    meta: { title: '床位管理' },
  },
  {
    path: '/ehr',
    name: 'ehr',
    component: () => import('../views/EhrList.vue'),
    meta: { title: '患者档案' },
  },
  {
    path: '/handovers',
    name: 'handovers',
    component: () => import('../views/Handovers.vue'),
    meta: { title: '交接班' },
  },
  {
    path: '/incidents',
    name: 'incidents',
    component: () => import('../views/Incidents.vue'),
    meta: { title: '异常事件' },
  },
  {
    path: '/care-records',
    name: 'care-records',
    component: () => import('../views/CareRecords.vue'),
    meta: { title: '护理记录' },
  },
  {
    path: '/payment-channels',
    name: 'payment-channels',
    component: () => import('../views/PaymentChannels.vue'),
    meta: { title: '支付渠道' },
  },
  {
    path: '/showcase',
    name: 'showcase',
    component: () => import('../views/Showcase.vue'),
    meta: { title: '组件展示' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫:未登录跳 /login
router.beforeEach((to) => {
  if (to.meta.guest) return true
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null
  if (!token && to.name !== 'login') {
    return { name: 'login' }
  }
  return true
})

// 更新 document.title
router.afterEach((to) => {
  const title = (to.meta as { title?: string }).title
  document.title = title ? `${title} · 智护银伴 v2` : '智护银伴 v2'
})

export default router
