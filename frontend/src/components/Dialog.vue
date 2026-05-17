<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, ref, nextTick } from 'vue'

/**
 * Dialog — 对话框
 *
 * 直接套用 ui.css 的 .dialog-ov / .dialog / .dialog-title / .dialog-body / .dialog-actions。
 *
 * 遵循 Phase 2 的"只换皮不换骨"原则:
 *   - 没有过渡组件,直接靠 ui.css 里 .dialog-ov 的 fade-in / .dialog 的 dialog-in 动画
 *   - ESC 关闭、点遮罩关闭 —— 这两个交互过去用 dialog.js 写,这里集成进 v-model
 *   - 不引入 vue-final-modal / focus-trap;Phase 4 起若有可访问性需求再加
 *
 * 使用:
 *   <Dialog v-model="open" title="确认" @confirm="...">
 *     正文
 *     <template #actions>
 *       <Btn variant="ghost" @click="open = false">取消</Btn>
 *       <Btn variant="primary" @click="confirm">确定</Btn>
 *     </template>
 *   </Dialog>
 */
const props = defineProps<{
  modelValue: boolean
  title?: string
  closeOnOverlay?: boolean
  closeOnEsc?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
}>()

const dialogEl = ref<HTMLElement | null>(null)

function close() {
  emit('update:modelValue', false)
}

function onOverlayClick(e: MouseEvent) {
  // 只有点中遮罩本身才关闭,点 dialog 内部不应关
  if (props.closeOnOverlay === false) return
  if (e.target === e.currentTarget) close()
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.closeOnEsc !== false && props.modelValue) {
    close()
  }
}

// 锁定背景滚动 —— 不引第三方 useScrollLock,自己保留 documentElement.style.overflow
let prevOverflow = ''
watch(
  () => props.modelValue,
  async (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      prevOverflow = document.documentElement.style.overflow
      document.documentElement.style.overflow = 'hidden'
      await nextTick()
      dialogEl.value?.focus()
    } else {
      document.documentElement.style.overflow = prevOverflow
    }
  },
  { immediate: true },
)

onMounted(() => {
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  // 防御性恢复,避免组件意外卸载留下 overflow:hidden
  if (typeof document !== 'undefined' && props.modelValue) {
    document.documentElement.style.overflow = prevOverflow
  }
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
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
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
