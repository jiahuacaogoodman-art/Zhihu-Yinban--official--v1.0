import { onBeforeUnmount, watch, type Ref } from 'vue'

/**
 * useFocusTrap — 把 Tab 焦点锁在指定容器内。
 *
 * Dialog / Drawer 等模态层必须的可访问性能力:
 *   1) 打开时把焦点移到首个可聚焦元素(或容器自身)
 *   2) Tab 走到末尾时回到首项;Shift+Tab 走到首项时回到末尾
 *   3) 关闭时把焦点还给打开它的元素
 *
 * 用法:
 *   const open = ref(false)
 *   const dialogEl = ref<HTMLElement | null>(null)
 *   useFocusTrap(open, dialogEl)
 */

const FOCUSABLE = [
  'a[href]:not([tabindex="-1"])',
  'area[href]:not([tabindex="-1"])',
  'button:not([disabled]):not([tabindex="-1"])',
  'input:not([disabled]):not([type="hidden"]):not([tabindex="-1"])',
  'select:not([disabled]):not([tabindex="-1"])',
  'textarea:not([disabled]):not([tabindex="-1"])',
  '[contenteditable="true"]:not([tabindex="-1"])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function getFocusable(root: HTMLElement): HTMLElement[] {
  const all = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE))
  return all.filter(
    (el) =>
      // 排掉隐藏的(display:none / visibility:hidden / 0 尺寸)
      el.offsetParent !== null || el === document.activeElement,
  )
}

export function useFocusTrap(
  active: Ref<boolean>,
  containerRef: Ref<HTMLElement | null | undefined>,
) {
  let previousFocus: HTMLElement | null = null

  function onKeydown(e: KeyboardEvent) {
    if (!active.value) return
    if (e.key !== 'Tab') return
    const root = containerRef.value
    if (!root) return
    const items = getFocusable(root)
    if (items.length === 0) {
      e.preventDefault()
      root.focus()
      return
    }
    const first = items[0]
    const last = items[items.length - 1]
    const current = document.activeElement as HTMLElement | null
    if (e.shiftKey) {
      if (current === first || !root.contains(current)) {
        e.preventDefault()
        last.focus()
      }
    } else {
      if (current === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }

  function activate() {
    if (typeof document === 'undefined') return
    previousFocus = (document.activeElement as HTMLElement | null) ?? null
    // 等容器渲染好(下一帧)再聚焦
    requestAnimationFrame(() => {
      const root = containerRef.value
      if (!root) return
      const items = getFocusable(root)
      const target = items[0] ?? root
      target.focus()
    })
    document.addEventListener('keydown', onKeydown, true)
  }

  function deactivate() {
    if (typeof document === 'undefined') return
    document.removeEventListener('keydown', onKeydown, true)
    if (previousFocus && typeof previousFocus.focus === 'function') {
      // 一些浏览器在元素已被卸载后调用 focus 会抛错
      try {
        previousFocus.focus()
      } catch {
        /* noop */
      }
    }
    previousFocus = null
  }

  watch(
    active,
    (v, prev) => {
      if (v && !prev) activate()
      else if (!v && prev) deactivate()
    },
    { immediate: false },
  )

  onBeforeUnmount(() => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('keydown', onKeydown, true)
    }
  })
}
