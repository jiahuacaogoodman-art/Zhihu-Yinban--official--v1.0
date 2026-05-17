<script setup lang="ts">
import { computed } from 'vue'

/**
 * Btn — 按钮组件
 *
 * 直接套用 ui.css 里的 .btn / .btn-primary / .btn-ghost / .btn-outline / .btn-danger / .btn-sm。
 * 不重写样式 —— RFC §8 兼容性矩阵:ui.css 0 改动。
 *
 * Props:
 *   variant — primary(默认) | ghost | outline | danger
 *   size    — md(默认,42px) | sm(34px)
 *   loading — true 时显示旋转环并禁用点击(沿用 .btn .ring 现有动画)
 *   tag     — 渲染成 <button> 还是 <a>。a 的样式 ui.css 已显式去掉下划线。
 *
 * 不做的事:
 *   - 不实现 icon-only 模式,等 Phase 3 第一个用到的视图再加
 *   - 不做"loading 时维持原宽度"的微交互,Phase 1 的痛点不在这
 */
const props = defineProps<{
  variant?: 'primary' | 'ghost' | 'outline' | 'danger'
  size?: 'md' | 'sm'
  loading?: boolean
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
  tag?: 'button' | 'a'
  href?: string
}>()

defineEmits<{
  click: [event: MouseEvent]
}>()

const classes = computed(() => [
  'btn',
  `btn-${props.variant ?? 'primary'}`,
  props.size === 'sm' ? 'btn-sm' : null,
])

const isDisabled = computed(() => props.disabled || props.loading)
</script>

<template>
  <a
    v-if="tag === 'a'"
    :class="classes"
    :href="isDisabled ? undefined : href"
    :aria-disabled="isDisabled || undefined"
    :tabindex="isDisabled ? -1 : undefined"
    @click="(e) => !isDisabled && $emit('click', e)"
  >
    <span v-if="loading" class="ring" aria-hidden="true" />
    <slot />
  </a>
  <button
    v-else
    :class="classes"
    :type="type ?? 'button'"
    :disabled="isDisabled"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="ring" aria-hidden="true" />
    <slot />
  </button>
</template>
