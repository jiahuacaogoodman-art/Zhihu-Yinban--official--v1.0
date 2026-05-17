import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

/**
 * 护工端 Router — 独立于管理端
 *
 * 路由:
 *   / → 老人列表(默认)
 *   /patient/:id → 患者详情 + 任务卡 + AI
 *
 * 鉴权:同样读 localStorage auth_token
 */

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'nurse-home',
    component: () => import('../nurse-views/PatientList.vue'),
    meta: { title: '老人列表' },
  },
  {
    path: '/patient/:id',
    name: 'nurse-patient',
    component: () => import('../nurse-views/PatientDetail.vue'),
    meta: { title: '患者详情' },
    props: true,
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 鉴权守卫
router.beforeEach((to) => {
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null
  if (!token) {
    // 护工端没有单独登录页,跳到管理端登录
    window.location.href = '/v2/#/login'
    return false
  }
  return true
})

router.afterEach((to) => {
  const title = (to.meta as { title?: string }).title
  document.title = title ? `${title} · 智护银伴 护工端` : '智护银伴 护工端'
})

export default router
