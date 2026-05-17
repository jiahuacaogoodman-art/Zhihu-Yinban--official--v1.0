import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

/**
 * Vue Router — Phase 3 起
 *
 * 使用 hash 模式 (/v2/#/beds) 而非 history 模式,原因:
 *   1) 后端 /v2 用 StaticFiles(html=True) 挂载;hash 变更不会触发服务端请求,
 *      不需要后端配 fallback catch-all(Phase 6 切 / 时再改 history 模式)。
 *   2) 旧版 / 已经用了 fragment (#billing / #ehr 等),保持同一惯例。
 *
 * 延迟加载视图(懒路由),避免首屏加载全部组件。
 */

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    // Phase 3: 首页先 redirect 到 beds(第一个试点视图)
    redirect: '/beds',
  },
  {
    path: '/beds',
    name: 'beds',
    component: () => import('../views/BedList.vue'),
    meta: { title: '床位管理' },
  },
  // Phase 3 只做 beds;后续 phase 逐步加其他视图:
  // { path: '/ehr', ... }
  // { path: '/billing', ... }
  // { path: '/handovers', ... }
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
  history: createWebHashHistory(),
  routes,
})

// 更新 document.title
router.afterEach((to) => {
  const title = (to.meta as { title?: string }).title
  document.title = title ? `${title} · 智护银伴 v2` : '智护银伴 v2'
})

export default router
