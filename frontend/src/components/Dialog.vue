<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, nextTick, toRef } from 'vue'
import { useScrollLock } from '../composables/useScrollLock'

/**
 * Dialog — 对话框 / Bottom Sheet / Full Sheet
 *
 * 直接套用 ui.css 的 .dialog-ov / .dialog / .dialog-title / .dialog-body /
 * .dialog-actions；移动端的 bottom-sheet 形态由 v2-mobile.css 接管。
 *
 * Phase 7 移动端深度适配的关键变化:
 *   1) 不再用 inline `documentElement.style.overflow='hidden'` —— 改用
 *      composables/useScrollLock，确保 iOS 上 body position:fixed 锁定，
 *      避免抽屉里滑动时背景一起滚。
 *   2) 多了 fullSheet prop:在 ≤640 时把 dialog 撑成全屏 sheet —— 给"详情
 *      / 大表单"用,移动端阅读编辑超大字段时不至于被卡死在 88dvh 高度里。
 *   3) 透明遮罩点击关闭 + ESC 关闭照旧;新增 :swipe-down(touch start/move/end)
 *      在 sheet 模式下下拉关闭。
 *
 * 使用:
 *   <Dialog v-model="open" title="确认">…</Dialog>
 *   <Dialog v-model="open" title="档案详情" full-sheet>…</Dialog>
 */
const props = defineProps<{
  modelValue: boolean
  title?: string
  closeOnOverlay?: boolean
  closeOnEsc?: boolean
  /** 在 ≤ 640 时撑满整屏(适合大表单/详情) */
  fullSheet?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
}>()

const dialogEl = ref<HTMLElement | null>(null)
const open = toRef(props, 'modelValue')

useScrollLock(open)

function close() {
  emit('update:modelValue', false)
}

function onOverlayClick(e: MouseEvent) {
  if (props.closeOnOverlay === false) return
  if (e.target === e.currentTarget) close()
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.closeOnEsc !== false && props.modelValue) {
    close()
  }
}

// ── 移动端下拉关闭 sheet ──
// 仅当 dialog 滚动到顶且向下拽 > 64px 时关闭。drag handle 区域(top 24px)
// 优先触发关闭,即便内容在中间也能下拉。
let touchStartY = 0
let touchStartScrollTop = 0
let dragging = false
let dragOffset = 0

function isMobileSheet() {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(max-width: 640px)').matches
}

function onTouchStart(e: TouchEvent) {
  if (!isMobileSheet()) return
  if (!dialogEl.value) return
  touchStartY = e.touches[0].clientY
  touchStartScrollTop = dialogEl.value.scrollTop
  dragging = touchStartScrollTop <= 0 // 顶部才允许下拉关闭
  dragOffset = 0
}

function onTouchMove(e: TouchEvent) {
  if (!dragging) return
  if (!dialogEl.value) return
  const dy = e.touches[0].clientY - touchStartY
  if (dy < 0) {
    dragOffset = 0
    dialogEl.value.style.transform = ''
    return
  }
  dragOffset = dy
  // 跟手位移,带阻尼
  dialogEl.value.style.transform = `translateY(${dy * 0.6}px)`
  dialogEl.value.style.transition = 'none'
}

function onTouchEnd() {
  if (!dragging) return
  if (!dialogEl.value) return
  dialogEl.value.style.transition = ''
  if (dragOffset > 96) {
    // 越过阈值 → 关闭
    close()
  } else {
    // 回弹
    dialogEl.value.style.transform = ''
  }
  dragging = false
  dragOffset = 0
}

watch(
  () => props.modelValue,
  async (v) => {
    if (v) {
      await nextTick()
      dialogEl.value?.focus()
      // 进入时清掉上一次的 transform(防止 v-if 复用残留)
      if (dialogEl.value) dialogEl.value.style.transform = ''
    }
  },
)

onMounted(() => {
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="dialog-ov"
      role="presentation"
      @click="onOverlayClick"
    >
      <div
        ref="dialogEl"
        class="dialog"
        :class="{ 'dialog--fullsheet': fullSheet }"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
        @touchstart.passive="onTouchStart"
        @touchmove.passive="onTouchMove"
        @touchend.passive="onTouchEnd"
        @touchcancel.passive="onTouchEnd"
      >
        <h2 v-if="title" class="dialog-title">{{ title }}</h2>
        <div class="dialog-body">
          <slot />
        </div>
        <div v-if="$slots.actions" class="dialog-actions">
          <slot name="actions" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
