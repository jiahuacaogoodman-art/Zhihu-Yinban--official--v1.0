import { createApp } from 'vue'
import App from './App.vue'

// Phase 2 起:复用全部静态设计系统。
// RFC §8 兼容性矩阵明确规定 tokens / glass / ui / mobile.css 0 改动 ——
// v2 直接以 CSS 引入这 4 份原 .css,vite 把它们打进 static/v2/assets/ 下,
// 与旧版 / / /nurse / /billing 引的是相同源文件,样式 100% 一致。
import '@design/tokens.css'
import '@design/glass.css'
import '@design/ui.css'
import '@design/mobile.css'

createApp(App).mount('#app')
