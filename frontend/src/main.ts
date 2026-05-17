import { createApp } from 'vue'
import App from './App.vue'

// Phase 1: 仅复用 tokens（基础变量）。glass.css / ui.css / mobile.css 留到 Phase 2
// 整体迁移成组件库时再 import，避免 v2 占位页加载一堆此刻用不上的 CSS。
// —— 见 RFC §6 路线图：Phase 1 只验证 "/v2/ 能打开 + Vite 能 build"
import '@design/tokens.css'
import './styles/phase1.css'

createApp(App).mount('#app')
