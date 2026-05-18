import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setOnUnauthorized } from './api'
import { useAuthStore } from './stores/auth'

// 复用全部静态设计系统(tokens / glass / ui / mobile.css 0 改动)
import '@design/tokens.css'
import '@design/glass.css'
import '@design/ui.css'
import '@design/mobile.css'
// 应用壳层移动端样式(layout / drawer / bottom-tab / dialog / toast / safe-area)
import './styles/app-shell.css'
// 子页面移动端专项优化(GlassPanel 卡片、列表触控、各 View 内部排版)
import './styles/views-mobile.css'

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
