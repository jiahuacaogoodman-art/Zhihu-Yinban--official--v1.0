import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/**
 * useNetworkStatus — 在线 / 离线监听。
 *
 * 用 navigator.onLine + 'online' / 'offline' 事件。Chrome 在地铁/电梯
 * 这种"网络很烂但 navigator.onLine = true"的场景里检测不准,但绝大
 * 多数情况下足够用 —— 真正断网时 (飞行模式 / 拔网线 / Wi-Fi 关闭) 一定会触发。
 *
 * 用法:
 *   const { online, offline } = useNetworkStatus()
 *
 * App.vue 顶部的 NetworkBanner 用 offline 来切显隐。
 */
export function useNetworkStatus(): { online: Ref<boolean>; offline: Ref<boolean> } {
  const online = ref(true)

  if (typeof navigator !== 'undefined' && typeof navigator.onLine === 'boolean') {
    online.value = navigator.onLine
  }

  const offline = ref(!online.value)

  function setOnline() {
    online.value = true
    offline.value = false
  }
  function setOffline() {
    online.value = false
    offline.value = true
  }

  onMounted(() => {
    if (typeof window === 'undefined') return
    window.addEventListener('online', setOnline)
    window.addEventListener('offline', setOffline)
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') return
    window.removeEventListener('online', setOnline)
    window.removeEventListener('offline', setOffline)
  })

  return { online, offline }
}
