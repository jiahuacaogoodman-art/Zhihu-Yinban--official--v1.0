import { onMounted, onBeforeUnmount, ref, type Ref } from 'vue'

/**
 * useMediaQuery — 响应式 matchMedia 包装
 *
 * 用于让 Vue 组件按媒体查询结果走分支渲染（而不是只靠 CSS 隐藏，
 * 因为 App.vue 在移动端要"完全不渲染桌面侧栏 / 改渲染抽屉"，
 * 单纯 display:none 不够）。
 *
 * 在 SSR / 测试环境（无 window）里安全地降级到 false。
 */
export function useMediaQuery(query: string): Ref<boolean> {
  const matches = ref(false)
  if (typeof window === 'undefined' || !window.matchMedia) {
    return matches
  }

  const mql = window.matchMedia(query)
  matches.value = mql.matches

  const onChange = (e: MediaQueryListEvent) => {
    matches.value = e.matches
  }

  onMounted(() => {
    // 现代浏览器
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onChange)
    } else if (typeof (mql as unknown as { addListener?: (cb: (e: MediaQueryListEvent) => void) => void }).addListener === 'function') {
      ;(mql as unknown as { addListener: (cb: (e: MediaQueryListEvent) => void) => void }).addListener(onChange)
    }
  })

  onBeforeUnmount(() => {
    if (typeof mql.removeEventListener === 'function') {
      mql.removeEventListener('change', onChange)
    } else if (typeof (mql as unknown as { removeListener?: (cb: (e: MediaQueryListEvent) => void) => void }).removeListener === 'function') {
      ;(mql as unknown as { removeListener: (cb: (e: MediaQueryListEvent) => void) => void }).removeListener(onChange)
    }
  })

  return matches
}

/**
 * 标准断点 —— 与 mobile.css / app-shell.css 保持一致。
 *   sm: ≤ 640px  手机
 *   md: ≤ 960px  平板/小笔记本
 */
export const useIsMobile = () => useMediaQuery('(max-width: 640px)')
export const useIsTabletOrBelow = () => useMediaQuery('(max-width: 960px)')
