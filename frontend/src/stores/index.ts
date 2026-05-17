/**
 * Pinia stores 入口
 *
 * 在 main.ts 里 `app.use(createPinia())` 即可;各 store 按功能域拆文件。
 * 本文件只做桶导出。
 */
export { useBedStore } from './beds'
export { useAuthStore } from './auth'
