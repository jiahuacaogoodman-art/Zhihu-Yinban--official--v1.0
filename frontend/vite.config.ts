/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/**
 * Vite 配置 — Phase 1 骨架
 *
 * 关键决策（见 RFC §5.1 / §5.3）：
 *   1) build.outDir 指向 ../static/v2/，让 FastAPI 的 StaticFiles 直接挂载即可。
 *      构建产物**不进 git**（见 .gitignore），由 CI 在镜像构建阶段产出。
 *   2) base 用 './'（相对路径）而非 '/v2/'，避免 v2 路径被改成 /legacy/v2/ 时
 *      静态资源 404；index.html 内的 <script src="./assets/..."> 都跟着走。
 *   3) emptyOutDir: true — 每次 build 清空 static/v2/，防止旧 hash 资源残留。
 *      这也是为什么不要把 static/v2/ 加进 git：手 stash/rebase 会把旧产物当未提交改动。
 *   4) Phase 1 只有一个 entry（管理端 v2）；Phase 5 加护工端时改成 rollupOptions.input
 *      多入口（managers + nurse），不需要现在加。
 */
export default defineConfig({
  plugins: [vue()],
  define: {
    // 构建时注入,占位页用来显示"这个 bundle 是什么时候打的"
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // 让 src/ 里的代码可以 import '@design/tokens.css' 直接复用现有设计系统
      // —— 见 RFC §8 兼容性矩阵：tokens / glass / ui / mobile.css 0 改动
      '@design': fileURLToPath(new URL('../static/design', import.meta.url)),
    },
  },
  base: './',
  build: {
    outDir: '../static/v2',
    emptyOutDir: true,
    sourcemap: true,
    // 控制 chunk 体积，避免 Vue + 业务一块儿打成单一 bundle
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue'],
        },
      },
    },
  },
  server: {
    port: 5173,
    // 开发态把 /api / /uploads / /health 转发到本地 FastAPI
    // 这样 dev server 不需要单独跑后端镜像
    proxy: {
      '/api': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
