<script setup lang="ts">
import { useToast, type ToastItem } from '../composables/useToast'

/**
 * Toast 容器 —— 整个应用挂载一次。
 *
 * 直接套用 ui.css 的 .toast-wrap / .toast / .toast-success / -error / -warning / -info。
 * 实际触发 toast 是通过 useToast() composable;这里只负责渲染队列。
 *
 * 用 Teleport 到 body 是为了避免被父级 transform/overflow 截断
 * (旧版 dialog.js 也是这么做的)。
 */
const { items, dismiss } = useToast()

function toneClass(tone: ToastItem['tone']) {
  return `toast-${tone}`
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-wrap" role="status" aria-live="polite">
      <div
        v-for="t in items"
        :key="t.id"
        class="toast"
        :class="toneClass(t.tone)"
        @click="dismiss(t.id)"
      >
        <span>{{ t.text }}</span>
      </div>
    </div>
  </Teleport>
</template>
