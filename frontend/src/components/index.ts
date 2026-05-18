/**
 * 基础组件桶导出 —— Phase 2 起,业务侧通过
 *   import { Btn, Field } from '@/components'
 * 直接拿到所有原件,而不必逐文件 import。
 *
 * 6 个原件清单见 docs/FRONTEND_REFACTOR_RFC.md §6.2 Phase 2。
 */
export { default as GlassPanel } from './GlassPanel.vue'
export { default as Btn } from './Btn.vue'
export { default as Field } from './Field.vue'
export { default as Chip } from './Chip.vue'
export { default as Dialog } from './Dialog.vue'
export { default as Toast } from './Toast.vue'

// Phase 8 移动端深度适配新增组件
export { default as Skeleton } from './Skeleton.vue'
export { default as PullToRefresh } from './PullToRefresh.vue'
export { default as NetworkBanner } from './NetworkBanner.vue'
