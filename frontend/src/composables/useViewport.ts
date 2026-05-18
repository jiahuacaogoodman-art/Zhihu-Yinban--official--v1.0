import { onBeforeUnmount, onMounted, reactive, toRefs, type ToRefs } from 'vue'

/**
 * useViewport — 监听 window.visualViewport 拿到"软键盘弹出"信号。
 *
 * 为什么:
 *   iOS Safari / Android Chrome 在软键盘弹出时,window.innerHeight 不会变,
 *   只有 visualViewport.height 变小。我们用 (window.innerHeight - vv.height)
 *   来推断"键盘高度";> 100 视为弹出。
 *
 *   桌面端这个值始终是 0 —— 不影响逻辑。
 *
 *   App.vue / NurseApp.vue 用这个数据来:
 *     1) 软键盘弹出时隐藏底部 tab(给输入框让位 + 防止被遮挡)
 *     2) Dialog 在键盘弹出时缩短 max-height
 *     3) Login 等聚焦输入框后自动滚动到合适位置
 *
 * SSR / 测试 (无 window) 安全降级到全 0。
 */

interface ViewportState {
  width: number
  height: number
  /** 推断的虚拟键盘高度(px)。无 visualViewport 或桌面恒为 0 */
  keyboardHeight: number
  /** keyboardHeight > 100 即视为键盘弹出 */
  keyboardOpen: boolean
  /** 屏幕方向 */
  orientation: 'portrait' | 'landscape'
}

const KB_OPEN_THRESHOLD = 100

export function useViewport(): ToRefs<ViewportState> {
  const state = reactive<ViewportState>({
    width: 0,
    height: 0,
    keyboardHeight: 0,
    keyboardOpen: false,
    orientation: 'portrait',
  })

  if (typeof window === 'undefined') {
    return toRefs(state)
  }

  function update() {
    const vv = window.visualViewport
    const w = vv?.width ?? window.innerWidth
    const h = vv?.height ?? window.innerHeight
    const kbH = vv ? Math.max(0, window.innerHeight - vv.height - (vv.offsetTop ?? 0)) : 0
    state.width = w
    state.height = h
    state.keyboardHeight = kbH
    state.keyboardOpen = kbH > KB_OPEN_THRESHOLD
    state.orientation = w >= h ? 'landscape' : 'portrait'
  }

  // 立即采样一次,确保 SSR 后客户端首屏数值正确
  update()

  onMounted(() => {
    update()
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', update)
      window.visualViewport.addEventListener('scroll', update)
    }
    window.addEventListener('resize', update)
    window.addEventListener('orientationchange', update)
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') return
    if (window.visualViewport) {
      window.visualViewport.removeEventListener('resize', update)
      window.visualViewport.removeEventListener('scroll', update)
    }
    window.removeEventListener('resize', update)
    window.removeEventListener('orientationchange', update)
  })

  return toRefs(state)
}
