import { reactive } from 'vue'

/**
 * useToast — 简单的全局 toast 队列。
 *
 * 设计取舍:
 *   - 不引 vue-toastification / sonner;Phase 2 没必要带新依赖
 *   - 队列是模块级 reactive,所有 import 共享同一份
 *     (旧 dialog.js 也是单例)
 *   - 默认 3 秒自动消失;duration:0 表示常驻
 *   - 不支持"按 id 更新"——首个用到的视图再加
 *
 * Phase 3 起 view 内一行就能调用:
 *   const { push } = useToast()
 *   push({ tone: 'success', text: '已保存' })
 */

export type ToastTone = 'success' | 'error' | 'warning' | 'info'

export interface ToastItem {
  id: number
  tone: ToastTone
  text: string
}

interface PushOptions {
  tone?: ToastTone
  text: string
  duration?: number
}

const state = reactive<{ items: ToastItem[] }>({ items: [] })
let nextId = 1

function push(opts: PushOptions) {
  const id = nextId++
  const tone = opts.tone ?? 'info'
  state.items.push({ id, tone, text: opts.text })
  const duration = opts.duration ?? 3000
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration)
  }
  return id
}

function dismiss(id: number) {
  const idx = state.items.findIndex((t) => t.id === id)
  if (idx >= 0) state.items.splice(idx, 1)
}

function clear() {
  state.items.splice(0, state.items.length)
}

export function useToast() {
  return {
    items: state.items,
    push,
    dismiss,
    clear,
  }
}
