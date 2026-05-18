import { onBeforeUnmount, watch, type Ref } from 'vue'

/**
 * useScrollLock — 抽屉/对话框打开时锁住背景滚动
 *
 * 之所以自己封一个而不是直接 document.documentElement.style.overflow = 'hidden':
 *   1) iOS Safari 仅 overflow:hidden 不够,手指还能拖动整页(地址栏弹出/收起会
 *      触发 viewport 重排,造成"抽屉打开期间内容跳动 + 抽屉错位")。需要再固
 *      定 body position: fixed + top = -scrollTop。
 *   2) 我们在 App.vue 抽屉 / Dialog / 多个全屏 sheet 都要用,引用计数防止"两个
 *      锁源依次关闭时,第一个关掉就放开背景"导致的 overflow 抖动。
 *
 * 用法:
 *   const open = ref(false)
 *   useScrollLock(open)
 *
 * 多个组件同时 watch 同一个 ref 是安全的,内部维护引用计数:0 → 上锁,> 0 → 不变,
 * 减回 0 → 解锁。
 */

let lockCount = 0
let savedScrollY = 0
let savedBodyStyle: {
  position: string
  top: string
  width: string
  overflow: string
} | null = null

function applyLock() {
  if (typeof document === 'undefined') return
  if (lockCount === 0) {
    savedScrollY = window.scrollY || document.documentElement.scrollTop || 0
    const body = document.body
    savedBodyStyle = {
      position: body.style.position,
      top: body.style.top,
      width: body.style.width,
      overflow: body.style.overflow,
    }
    body.style.position = 'fixed'
    body.style.top = `-${savedScrollY}px`
    body.style.width = '100%'
    body.style.overflow = 'hidden'
  }
  lockCount++
}

function releaseLock() {
  if (typeof document === 'undefined') return
  if (lockCount === 0) return
  lockCount--
  if (lockCount === 0 && savedBodyStyle) {
    const body = document.body
    body.style.position = savedBodyStyle.position
    body.style.top = savedBodyStyle.top
    body.style.width = savedBodyStyle.width
    body.style.overflow = savedBodyStyle.overflow
    window.scrollTo(0, savedScrollY)
    savedBodyStyle = null
  }
}

export function useScrollLock(open: Ref<boolean>) {
  let locked = false

  watch(
    open,
    (v) => {
      if (v && !locked) {
        applyLock()
        locked = true
      } else if (!v && locked) {
        releaseLock()
        locked = false
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    if (locked) {
      releaseLock()
      locked = false
    }
  })
}
