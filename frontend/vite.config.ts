/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { resolve } from 'node:path'

/**
 * Vite 配置 — Phase 5 多入口
 *
 * 关键决策（见 RFC §5.1 / §5.3 / §6.5）：
 *   1) build.outDir 指向 ../static/v2/，让 FastAPI 的 StaticFiles 直接挂载即可。
 *   2) base 用 './'（相对路径）。
 *   3) emptyOutDir: true — 每次 build 清空 static/v2/。
 *   4) Phase 5: rollupOptions.input 配置两个入口
 *      - managers: index.html → 管理端 SPA
 *      - nurse: nurse.html → 护工端 SPA
 *      构建产物:
 *        static/v2/index.html      (管理端)
 *        static/v2/nurse.html      (护工端)
 *        static/v2/assets/...      (共享 chunk)
 */
export default defineConfig({
  plugins: [vue()],
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@design': fileURLToPath(new URL('../static/design', import.meta.url)),
    },
  },
  base: './',
  build: {
    outDir: '../static/v2',
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      input: {
        managers: resolve(__dirname, 'index.html'),
        nurse: resolve(__dirname, 'nurse.html'),
      },
      output: {
        manualChunks: {
          vue: ['vue'],
          'vue-router': ['vue-router'],
          pinia: ['pinia'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
