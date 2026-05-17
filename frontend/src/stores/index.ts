/**
 * Pinia stores 入口 —— Phase 3 起
 *
 * 在 main.ts 里 `app.use(createPinia())` 即可;各 store 按功能域拆文件:
 *   stores/beds.ts    — 床位状态
 *   stores/auth.ts    — 登录 token / user info (Phase 4)
 *   ...
 *
 * 本文件只做桶导出。
 */
export { useBedStore } from './beds'
