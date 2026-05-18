import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setOnUnauthorized } from './api'
import { useAuthStore } from './stores/auth'

// Phase 2 起:复用全部静态设计系统。
// RFC §8 兼容性矩阵明确规定 tokens / glass / ui / mobile.css 0 改动
import '@design/tokens.css'
import '@design/glass.css'
import '@design/ui.css'
import '@design/mobile.css'
// Phase 7 移动端深度适配 —— 仅作用于 v2 Vue 端组件，不动 design/* 任何文件
import './styles/v2-mobile.css'
// Phase 8 子页面移动端专项优化（GlassPanel 卡片、列表触控、各 View 内部排版）
import './styles/v2-views-mobile.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// Phase 7 起:任何 401 → 自动登出 + 跳登录(带 redirect)
//
// 必须在 app.use(pinia) 之后注册,否则 useAuthStore() 会报"no active pinia"。
setOnUnauthorized(() => {
  const auth = useAuthStore()
  auth.logout()
  // 当前已经在 /login 就不重复跳
  const cur = router.currentRoute.value
  if (cur.name === 'login') return
  const redirect = cur.fullPath
  router.replace({
    name: 'login',
    query: redirect && redirect !== '/' ? { redirect } : undefined,
  })
})

app.mount('#app')
