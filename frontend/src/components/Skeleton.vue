<script setup lang="ts">
import { computed } from 'vue'

/**
 * Skeleton — 占位屏(shimmer 加载动画)
 *
 * 替代之前到处散落的 <div class="skel" style="height: 200px;"> 写法。
 * 之所以单独抽:
 *   1) shape: card / line / circle / row 四种最常见占位形态,业务侧不需要
 *      自己拼 height/border-radius
 *   2) count: 一行写 5 个占位卡(SkeletonGroup 在 .stack 里 v-for 太啰嗦)
 *   3) 默认在 prefers-reduced-motion 下停用 shimmer 动画
 *
 * 用法:
 *   <Skeleton shape="card" :count="3" />
 *   <Skeleton shape="line" width="60%" />
 *   <Skeleton shape="circle" size="44px" />
 */
const props = defineProps<{
  /** 形状:card 大块卡片,line 单行文本占位,circle 头像占位,row 列表行 */
  shape?: 'card' | 'line' | 'circle' | 'row'
  /** 数量(默认 1)。多行时上下间距由组件自管 */
  count?: number
  /** 宽度(任意 CSS 长度) */
  width?: string
  /** 高度(任意 CSS 长度;card / row 时也可指定单行高度) */
  height?: string
  /** circle 形态的直径(优先级高于 width/height) */
  size?: string
  /** 圆角覆盖 */
  radius?: string
  /** 关闭 shimmer 动画(默认开,但 prefers-reduced-motion 自动关) */
  noAnim?: boolean
}>()

const list = computed(() => Array.from({ length: props.count ?? 1 }, (_, i) => i))

const shape = computed(() => props.shape ?? 'line')
const baseStyle = computed(() => {
  const s: Record<string, string> = {}
  if (shape.value === 'circle') {
    const d = props.size ?? '40px'
    s.width = d
    s.height = d
    s.borderRadius = '50%'
  } else if (shape.value === 'card') {
    s.width = props.width ?? '100%'
    s.height = props.height ?? '120px'
    s.borderRadius = props.radius ?? '14px'
  } else if (shape.value === 'row') {
    s.width = props.width ?? '100%'
    s.height = props.height ?? '64px'
    s.borderRadius = props.radius ?? '12px'
  } else {
    s.width = props.width ?? '100%'
    s.height = props.height ?? '14px'
    s.borderRadius = props.radius ?? '6px'
  }
  return s
})
</script>

<template>
  <div
    class="skel-group"
    :class="{ 'skel-group--lines': shape === 'line', 'skel-group--anim': !noAnim }"
    role="status"
    aria-label="加载中"
    aria-live="polite"
  >
    <span
      v-for="i in list"
      :key="i"
      class="skel-item"
      :style="baseStyle"
    />
  </div>
</template>

<style scoped>
.skel-group {
  display: grid;
  gap: 8px;
}
.skel-item {
  display: block;
  background: linear-gradient(
    90deg,
    rgba(15, 23, 42, 0.05) 0%,
    rgba(15, 23, 42, 0.10) 50%,
    rgba(15, 23, 42, 0.05) 100%
  );
  background-size: 200% 100%;
  background-position: 0 0;
}
.skel-group--anim .skel-item {
  animation: skel-shimmer 1.4s ease-in-out infinite;
}
@keyframes skel-shimmer {
  0% { background-position: 0 0; }
  100% { background-position: -200% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .skel-group--anim .skel-item {
    animation: none;
    background-position: 50% 0;
  }
}
</style>
