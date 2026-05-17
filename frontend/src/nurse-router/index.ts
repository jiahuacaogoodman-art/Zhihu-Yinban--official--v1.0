import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

/**
 * 护工端 Router — Phase 6: history mode
 *
 * 路由:
 *   /nurse/ → 老人列表
 *   /nurse/patient/:id → 患者详情 + 任务卡 + AI
 *
 * 后端 /nurse 返回 static/v2/nurse.html(SPA),所有子路径
 * 由 Vue Router 在客户端处理。
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
  history: createWebHistory('/nurse'),
  routes,
})

// 鉴权守卫
router.beforeEach((to) => {
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null
  if (!token) {
    // 跳到管理端登录页
    window.location.href = '/login'
    return false
  }
  return true
})

router.afterEach((to) => {
  const title = (to.meta as { title?: string }).title
  document.title = title ? `${title} · 智护银伴 护工端` : '智护银伴 护工端'
})

export default router
