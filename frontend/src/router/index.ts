import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

/**
 * 管理端 Router — 保留双端架构，管理端补齐全部功能页。
 * 护工端仍然是独立入口 nurse.html → nurse-main.ts → nurse-router。
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
  // ── 核心功能 ──
  {
    path: '/nursing-decision',
    name: 'nursing-decision',
    component: () => import('../views/NursingDecision.vue'),
    meta: { title: 'AI 护理建议' },
  },
  {
    path: '/ehr/add',
    name: 'ehr-add',
    component: () => import('../views/PatientAdd.vue'),
    meta: { title: '录入档案' },
  },
  {
    path: '/ehr',
    name: 'ehr',
    component: () => import('../views/EhrList.vue'),
    meta: { title: '患者档案' },
  },
  {
    path: '/ehr/upload',
    name: 'ehr-upload',
    component: () => import('../views/MedicalUpload.vue'),
    meta: { title: '病历上传' },
  },
  {
    path: '/beds',
    name: 'beds',
    component: () => import('../views/BedList.vue'),
    meta: { title: '床位管理' },
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
  // ── 管理功能 ──
  {
    path: '/billing',
    name: 'billing',
    component: () => import('../views/Billing.vue'),
    meta: { title: '缴费管理' },
  },
  {
    path: '/payment-channels',
    name: 'payment-channels',
    component: () => import('../views/PaymentChannels.vue'),
    meta: { title: '支付渠道' },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('../views/UserManagement.vue'),
    meta: { title: '用户管理' },
  },
  {
    path: '/audit',
    name: 'audit',
    component: () => import('../views/AuditLog.vue'),
    meta: { title: '审计日志' },
  },
  // ── 兜底 ──
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

router.beforeEach((to) => {
  if (to.meta.guest) return true
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null
  if (!token && to.name !== 'login') {
    return {
      name: 'login',
      query: to.fullPath && to.fullPath !== '/' ? { redirect: to.fullPath } : undefined,
    }
  }
  return true
})

router.afterEach((to) => {
  const title = (to.meta as { title?: string }).title
  document.title = title ? `${title} · 智护银伴` : '智护银伴'
})

export default router
