import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// Phase 2 起:复用全部静态设计系统。
// RFC §8 兼容性矩阵明确规定 tokens / glass / ui / mobile.css 0 改动
import '@design/tokens.css'
import '@design/glass.css'
import '@design/ui.css'
import '@design/mobile.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
