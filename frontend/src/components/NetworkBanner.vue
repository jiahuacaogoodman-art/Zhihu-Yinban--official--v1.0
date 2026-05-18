<script setup lang="ts">
import { ref, watch } from 'vue'
import { useNetworkStatus } from '../composables/useNetworkStatus'

/**
 * NetworkBanner — 离线条幅
 *
 * 仅在 offline 时显示一条红色提示条;恢复在线后保留 2.5s "已恢复" 绿条
 * 再消失。这样用户能直观看到 "刚才确实断过 → 现在好了"。
 *
 * 一律用 fixed 定位贴在屏幕顶部(管理端 / 护工端通用),z-index 高于 appbar。
 *
 * 不绑全局 store,直接用 useNetworkStatus 自管,App.vue / NurseApp.vue
 * 各自挂一个就行。
 */
const { offline } = useNetworkStatus()

const showRestored = ref(false)
let restoredTimer: number | null = null

watch(offline, (now, prev) => {
  if (typeof window === 'undefined') return
  if (prev === true && now === false) {
    // 刚刚从离线恢复
    showRestored.value = true
    if (restoredTimer !== null) window.clearTimeout(restoredTimer)
    restoredTimer = window.setTimeout(() => {
      showRestored.value = false
      restoredTimer = null
    }, 2500)
  } else if (now === true) {
    // 又离线了:把 restored 状态清掉
    showRestored.value = false
    if (restoredTimer !== null) {
      window.clearTimeout(restoredTimer)
      restoredTimer = null
    }
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="netbanner">
      <div
        v-if="offline"
        class="netbanner netbanner--offline"
        role="status"
        aria-live="polite"
      >
        <span class="netbanner-icon" aria-hidden="true">⚠</span>
        <span class="netbanner-text">网络已断开 · 请检查 Wi-Fi 或蜂窝数据</span>
      </div>
      <div
        v-else-if="showRestored"
        class="netbanner netbanner--online"
        role="status"
        aria-live="polite"
      >
        <span class="netbanner-icon" aria-hidden="true">✓</span>
        <span class="netbanner-text">网络已恢复</span>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.netbanner {
  position: fixed;
  top: calc(env(safe-area-inset-top, 0px));
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 14px;
  font: 600 13px/1.4 var(--font-ui);
  letter-spacing: 0.02em;
  text-align: center;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.12);
}
.netbanner--offline {
  background: #dc2626;
  color: #fff;
}
.netbanner--online {
  background: #10b981;
  color: #fff;
}
.netbanner-icon {
  font-size: 14px;
  line-height: 1;
}

.netbanner-enter-active,
.netbanner-leave-active {
  transition: transform 280ms cubic-bezier(0.2, 0.8, 0.2, 1),
              opacity 220ms ease;
}
.netbanner-enter-from,
.netbanner-leave-to {
  transform: translateY(-110%);
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .netbanner-enter-active,
  .netbanner-leave-active {
    transition: opacity 200ms ease;
  }
  .netbanner-enter-from,
  .netbanner-leave-to {
    transform: none;
  }
}
</style>
