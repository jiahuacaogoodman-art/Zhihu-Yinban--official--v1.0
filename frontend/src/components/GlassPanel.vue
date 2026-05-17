<script setup lang="ts">
/**
 * GlassPanel — 通用玻璃容器
 *
 * 设计原则(RFC §8):0 改动 design system。本组件只是把现有 CSS class
 * 封装成 Vue 组件,不重写任何样式。
 *
 * 现有 ui.css 里 ".evidence-panel" 是最贴近"通用玻璃面板"的 class
 * (rgba(255,255,255,0.55) + blur(14px) saturate(150%) + 圆角 + 边框)。
 * 这里直接复用它当默认外观;后续若需要更轻/更重的 panel,再加 variant。
 *
 * Props:
 *   variant — "panel" (默认) | "card"
 *     - panel:用于嵌入式区块(evidence-panel 风格)
 *     - card :用于独立卡片(更不透明的背景,适合首屏 hero)
 *   tag — 渲染的根标签(默认 section,用于语义化)
 *
 * Slots:
 *   header (可选) — 顶部标题栏
 *   default — 主体
 *   footer (可选) — 底部操作区
 */
defineProps<{
  variant?: 'panel' | 'card'
  tag?: keyof HTMLElementTagNameMap
}>()
</script>

<template>
  <component
    :is="tag ?? 'section'"
    class="vp-glass"
    :class="`vp-glass--${variant ?? 'panel'}`"
  >
    <header v-if="$slots.header" class="vp-glass__header">
      <slot name="header" />
    </header>
    <div class="vp-glass__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="vp-glass__footer">
      <slot name="footer" />
    </footer>
  </component>
</template>

<style scoped>
/* 注意:这是 Phase 2 唯一新写的 CSS,且只有"组合现有 token"的简单规则。
   颜色/模糊参数全部来自 tokens.css,不引入新视觉语言。 */
.vp-glass {
  border-radius: var(--r-m, 14px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85), 0 4px 12px rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(14px) saturate(150%);
  -webkit-backdrop-filter: blur(14px) saturate(150%);
}
.vp-glass--panel {
  background: rgba(255, 255, 255, 0.55);
  padding: var(--sp-4, 16px);
}
.vp-glass--card {
  background: rgba(255, 255, 255, 0.92);
  padding: var(--sp-5, 20px);
  border-radius: var(--r-l, 18px);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95), var(--shadow-4, 0 24px 48px rgba(15, 23, 42, 0.16));
}
.vp-glass__header {
  margin-bottom: var(--sp-3, 12px);
  display: flex;
  align-items: center;
  gap: var(--sp-2, 8px);
}
.vp-glass__footer {
  margin-top: var(--sp-3, 12px);
  display: flex;
  gap: var(--sp-2, 8px);
  justify-content: flex-end;
}
</style>
