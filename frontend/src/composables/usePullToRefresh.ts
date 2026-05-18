import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/**
 * usePullToRefresh — 移动端常见的"下拉刷新"手势。
 *
 * 设计取舍:
 *   - 不引第三方库;原生 touch 事件就够了,体积成本零
 *   - 仅当容器 scrollTop === 0 时才接管手势(避免页内滚动被劫持)
 *   - 使用阻尼曲线(0.5 折扣 + sqrt 平滑)让下拉感觉跟手且不至于无限拉
 *   - 触发阈值 64px;触发后呼出 onRefresh,期间锁定后续触发
 *   - PointerEvent 在桌面 / 平板都行得通,但移动 iOS 部分浏览器对 pointer
 *     的兼容性不如 touch,这里用 touch + 仅 type=touchscreen 触发
 *
 * 用法:
 *   <PullToRefresh @refresh="reload">…</PullToRefresh>
 *
 *   // 或在自己的视图里用 ref:
 *   const wrap = ref<HTMLElement | null>(null)
 *   const { offset, refreshing } = usePullToRefresh(wrap, async () => {
 *     await reload()
 *   })
 */

interface UsePullToRefreshOptions {
  /** 下拉到多少 px 才触发(默认 64) */
  threshold?: number
  /** 阻尼系数(默认 0.5) */
  damping?: number
  /** 最大下拉位移(默认 96) */
  maxOffset?: number
  /** 是否启用(可外部禁用,例如桌面端) */
  enabled?: Ref<boolean>
}

export interface PullToRefreshState {
  /** 当前下拉位移(px),内容区可以用 transform: translateY 接 */
  offset: Ref<number>
  /** 当前是否正在刷新 */
  refreshing: Ref<boolean>
  /** 是否已超过阈值(用于切换"释放刷新"文案) */
  reached: Ref<boolean>
}

export function usePullToRefresh(
  containerRef: Ref<HTMLElement | null | undefined>,
  onRefresh: () => Promise<unknown> | unknown,
  opts: UsePullToRefreshOptions = {},
): PullToRefreshState {
  const threshold = opts.threshold ?? 64
  const damping = opts.damping ?? 0.5
  const maxOffset = opts.maxOffset ?? 96

  const offset = ref(0)
  const refreshing = ref(false)
  const reached = ref(false)

  let startY = 0
  let pulling = false

  function isScrollAtTop(el: HTMLElement): boolean {
    // 容器自己滚动 → 看 scrollTop;否则看 window scroll
    if (el.scrollHeight > el.clientHeight) {
      return el.scrollTop <= 0
    }
    if (typeof window === 'undefined') return false
    return (window.scrollY || document.documentElement.scrollTop || 0) <= 0
  }

  function isEnabled(): boolean {
    if (opts.enabled && opts.enabled.value === false) return false
    if (refreshing.value) return false
    return true
  }

  function onTouchStart(e: TouchEvent) {
    if (!isEnabled()) return
    const el = containerRef.value
    if (!el) return
    if (!isScrollAtTop(el)) return
    if (e.touches.length !== 1) return
    startY = e.touches[0].clientY
    pulling = true
  }

  function onTouchMove(e: TouchEvent) {
    if (!pulling) return
    const dy = e.touches[0].clientY - startY
    if (dy <= 0) {
      offset.value = 0
      reached.value = false
      return
    }
    // 阻尼:位移 = damping * sqrt(dy * threshold) —— 越拉越费劲
    const eased = Math.min(maxOffset, damping * Math.sqrt(dy * threshold))
    offset.value = eased
    reached.value = eased >= threshold * 0.85
  }

  async function onTouchEnd() {
    if (!pulling) return
    pulling = false
    const triggered = offset.value >= threshold * 0.85
    if (triggered && !refreshing.value) {
      refreshing.value = true
      // 保留一个"加载位"的位移,提示视觉上正在刷新
      offset.value = threshold * 0.7
      try {
        await onRefresh()
      } finally {
        refreshing.value = false
        offset.value = 0
        reached.value = false
      }
    } else {
      offset.value = 0
      reached.value = false
    }
  }

  function onTouchCancel() {
    pulling = false
    if (!refreshing.value) offset.value = 0
    reached.value = false
  }

  let attached: HTMLElement | null = null
  function attach() {
    const el = containerRef.value
    if (!el || attached === el) return
    detach()
    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchmove', onTouchMove, { passive: true })
    el.addEventListener('touchend', onTouchEnd, { passive: true })
    el.addEventListener('touchcancel', onTouchCancel, { passive: true })
    attached = el
  }
  function detach() {
    if (!attached) return
    attached.removeEventListener('touchstart', onTouchStart)
    attached.removeEventListener('touchmove', onTouchMove)
    attached.removeEventListener('touchend', onTouchEnd)
    attached.removeEventListener('touchcancel', onTouchCancel)
    attached = null
  }

  onMounted(() => {
    attach()
    // 容器懒加载场景:延迟一帧再尝试附加,确保 v-if 真挂上
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(attach)
    }
  })
  onBeforeUnmount(detach)

  return { offset, refreshing, reached }
}
