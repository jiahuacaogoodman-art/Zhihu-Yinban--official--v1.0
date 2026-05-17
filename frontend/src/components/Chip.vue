<script setup lang="ts">
import { computed } from 'vue'

/**
 * Chip — 标签
 *
 * 直接套用 ui.css 的 .chip / .chip-accent / .chip-red / .chip-amber / .chip-green / .chip-blue。
 *
 * 用 tone 而非 color 命名,与 ui.css 的语义一致(状态色而非品牌色)。
 * accent  → 强调(护理重点 / 主动) — chip-accent
 * danger  → 红 — chip-red
 * warning → 黄 — chip-amber
 * success → 绿 — chip-green
 * info    → 蓝 — chip-blue
 * neutral → 默认灰玻璃 — 仅 .chip 不带后缀
 *
 * 这里不暴露 chip-red 这种 raw class 名,是因为业务语义会变(比如以后产品要把
 * "红"换成"紫"),但"danger"这层抽象不会变。
 */
const props = defineProps<{
  tone?: 'neutral' | 'accent' | 'danger' | 'warning' | 'success' | 'info'
}>()

const cls = computed(() => {
  switch (props.tone ?? 'neutral') {
    case 'accent':
      return ['chip', 'chip-accent']
    case 'danger':
      return ['chip', 'chip-red']
    case 'warning':
      return ['chip', 'chip-amber']
    case 'success':
      return ['chip', 'chip-green']
    case 'info':
      return ['chip', 'chip-blue']
    default:
      return ['chip']
  }
})
</script>

<template>
  <span :class="cls">
    <slot />
  </span>
</template>
