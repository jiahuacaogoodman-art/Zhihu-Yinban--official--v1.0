import { onBeforeUnmount, onMounted, type Ref } from 'vue'

/**
 * useSwipeBack — 屏幕左边缘右滑返回(iOS Native 风格)
 *
 * 仅识别"从屏幕左边缘 24px 内开始 + 横向滑动 > 80px + 主要是横向(|dy| < dx)"
 * 的手势,匹配上就调 onBack(通常是 router.back())。
 *
 * 不接管:
 *   - 桌面端(无 touch)
 *   - 在 input/textarea/scrollable 容器内的拖动(用 e.target.closest 判断)
 *   - opts.enabled.value === false 时
 *
 * 用法:
 *   useSwipeBack(() => router.back())
 */

interface SwipeBackOptions {
  /** 起手区宽度(px,默认 24) */
  edgeWidth?: number
  /** 触发阈值(px,默认 80) */
  threshold?: number
  /** 是否启用(可禁用,如详情页里有水平滑动 carousel 时) */
  enabled?: Ref<boolean>
}

export function useSwipeBack(onBack: () => void, opts: SwipeBackOptions = {}) {
  const edgeWidth = opts.edgeWidth ?? 24
  const threshold = opts.threshold ?? 80

  let startX = 0
  let startY = 0
  let tracking = false
  let target: EventTarget | null = null

  function shouldIgnore(t: EventTarget | null): boolean {
    if (!t || !(t instanceof Element)) return false
    // 在表单控件内不触发
    if (t.closest('input, textarea, select, [contenteditable="true"]')) return true
    // 显式标注 data-no-swipeback 的容器(carousel 等)
    if (t.closest('[data-no-swipeback]')) return true
    return false
  }

  function onTouchStart(e: TouchEvent) {
    if (opts.enabled && opts.enabled.value === false) return
    if (e.touches.length !== 1) return
    const t = e.touches[0]
    if (t.clientX > edgeWidth) return
    if (shouldIgnore(e.target)) return
    startX = t.clientX
    startY = t.clientY
    tracking = true
    target = e.target
  }

  function onTouchMove(e: TouchEvent) {
    if (!tracking) return
    const t = e.touches[0]
    const dx = t.clientX - startX
    const dy = Math.abs(t.clientY - startY)
    // 主要竖直方向 → 放弃,交给页面滚动
    if (dy > Math.abs(dx) + 6) {
      tracking = false
    }
  }

  function onTouchEnd(e: TouchEvent) {
    if (!tracking) return
    tracking = false
    const t = e.changedTouches[0]
    const dx = t.clientX - startX
    const dy = Math.abs(t.clientY - startY)
    if (dx >= threshold && dy < threshold) {
      onBack()
    }
    target = null
  }

  function onTouchCancel() {
    tracking = false
    target = null
  }

  onMounted(() => {
    if (typeof document === 'undefined') return
    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchmove', onTouchMove, { passive: true })
    document.addEventListener('touchend', onTouchEnd, { passive: true })
    document.addEventListener('touchcancel', onTouchCancel, { passive: true })
  })

  onBeforeUnmount(() => {
    if (typeof document === 'undefined') return
    document.removeEventListener('touchstart', onTouchStart)
    document.removeEventListener('touchmove', onTouchMove)
    document.removeEventListener('touchend', onTouchEnd)
    document.removeEventListener('touchcancel', onTouchCancel)
  })
}
