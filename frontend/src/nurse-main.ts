import { createApp } from 'vue'
import { createPinia } from 'pinia'
import NurseApp from './nurse-views/NurseApp.vue'
import nurseRouter from './nurse-router'
import { setOnUnauthorized } from './api'
import { useAuthStore } from './stores/auth'

// 复用管理端的设计系统 —— RFC §8: 0 改动
import '@design/tokens.css'
import '@design/glass.css'
import '@design/ui.css'
import '@design/mobile.css'
// Phase 7 移动端深度适配（与管理端共享同一份 v2-mobile.css）
import './styles/v2-mobile.css'

const app = createApp(NurseApp)
app.use(createPinia())
app.use(nurseRouter)

// Phase 7 起:任何 401 → 清 token 并跳管理端登录页
//
// 护工端没有自己的登录页,统一走管理端 /login(login 拿到 token 后会带回所有 SPA)。
setOnUnauthorized(() => {
  const auth = useAuthStore()
  auth.logout()
  // 用 location 而不是 nurse-router,因为登录页在 / 域下、是另一个 SPA 入口
  if (typeof window !== 'undefined') {
    window.location.href = '/login?redirect=/nurse'
  }
})

app.mount('#app')
