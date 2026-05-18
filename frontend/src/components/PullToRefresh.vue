<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { usePullToRefresh } from '../composables/usePullToRefresh'
import { useIsTabletOrBelow } from '../composables/useMediaQuery'

/**
 * PullToRefresh — 移动端"下拉刷新"包裹组件
 *
 * 用法:
 *   <PullToRefresh @refresh="reload">
 *     <BedList />
 *   </PullToRefresh>
 *
 * 桌面端默认禁用(force 强制启用,例如希望平板触屏也用)。
 * 内部用 usePullToRefresh composable 处理手势 + 阻尼。
 */
const props = defineProps<{
  /** 阈值 px;默认 64 */
  threshold?: number
  /** 桌面端是否启用(默认 false) */
  enableOnDesktop?: boolean
  /** 加载文案 */
  loadingText?: string
  /** 拉到阈值前的提示文案 */
  pullText?: string
  /** 拉到阈值后的提示文案 */
  releaseText?: string
}>()

const emit = defineEmits<{
  refresh: [done: () => void]
}>()

const isMobile = useIsTabletOrBelow()
const enabled = computed(() => props.enableOnDesktop || isMobile.value)
const wrap = useTemplateRef<HTMLElement>('wrap')

const { offset, refreshing, reached } = usePullToRefresh(
  wrap,
  () =>
    new Promise<void>((resolve) => {
      // emit 出去,业务侧调用 done 关闭刷新态
      emit('refresh', resolve)
      // 兜底:如果业务忘了调 done,3 秒后自动 resolve
      setTimeout(resolve, 3000)
    }),
  { threshold: props.threshold, enabled },
)

const indicatorStyle = computed(() => ({
  transform: `translateY(${Math.max(0, offset.value - 32)}px)`,
  opacity: Math.min(1, offset.value / 32),
}))

const contentStyle = computed(() => ({
  transform: `translateY(${offset.value}px)`,
  transition: offset.value === 0 ? 'transform 240ms cubic-bezier(0.2, 0.8, 0.2, 1)' : 'none',
}))

const indicatorText = computed(() => {
  if (refreshing.value) return props.loadingText ?? '正在刷新…'
  if (reached.value) return props.releaseText ?? '释放刷新'
  return props.pullText ?? '下拉刷新'
})
</script>

<template>
  <div ref="wrap" class="ptr-wrap">
    <div
      v-if="enabled"
      class="ptr-indicator"
      :class="{ 'ptr-indicator--active': refreshing || reached }"
      :style="indicatorStyle"
      aria-hidden="true"
    >
      <svg
        class="ptr-spinner"
        :class="{ 'ptr-spinner--spin': refreshing }"
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          cx="12"
          cy="12"
          r="9"
          stroke="currentColor"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-dasharray="42 14"
        />
      </svg>
      <span class="ptr-text">{{ indicatorText }}</span>
    </div>
    <div class="ptr-content" :style="contentStyle">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ptr-wrap {
  position: relative;
  /* 不接管自身滚动:留给业务自己决定容器是否可滚动 */
  width: 100%;
}
.ptr-indicator {
  position: absolute;
  top: -36px;
  left: 0;
  right: 0;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--ink-3, #475569);
  font: 500 12px/1 var(--font-ui);
  pointer-events: none;
  z-index: 1;
}
.ptr-indicator--active {
  color: var(--accent-ink, #0f766e);
}
.ptr-spinner {
  display: inline-block;
}
.ptr-spinner--spin {
  animation: ptr-spin 800ms linear infinite;
}
@keyframes ptr-spin {
  to { transform: rotate(360deg); }
}
.ptr-content {
  will-change: transform;
}
@media (prefers-reduced-motion: reduce) {
  .ptr-spinner--spin { animation-duration: 2s; }
}
</style>
