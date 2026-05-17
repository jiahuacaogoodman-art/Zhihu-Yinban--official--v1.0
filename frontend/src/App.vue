<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel, Toast } from './components'
import { useToast } from './composables/useToast'

/**
 * Phase 2 展示页 ——
 *   不是产品页,而是 6 个基础原件的可视化用例库。Reviewer 打开 /v2/ 应该能
 *   亲眼看到每个原件被实例化、与 ui.css 已有视觉一致(玻璃 + tokens 配色)。
 *
 * Phase 3 起,这个 App.vue 会被 router-view 替代;但保留这个 showcase 思路,
 * 把它移到 /v2/playground 之类的内部页方便后续团队 review 设计漂移。
 */

const buildTime = __BUILD_TIME__
const health = ref<string>('checking...')
const dialogOpen = ref(false)
const inputText = ref('')
const careLevel = ref('care-2')

const { push } = useToast()

onMounted(async () => {
  try {
    const res = await fetch('/health', { cache: 'no-store' })
    if (!res.ok) {
      health.value = `unreachable (${res.status})`
      return
    }
    const data = await res.json()
    health.value = data.status ?? 'unknown'
  } catch {
    health.value = 'unreachable'
  }
})

function fireToast(tone: 'success' | 'error' | 'warning' | 'info') {
  const messages: Record<typeof tone, string> = {
    success: '已保存,数据写入成功',
    error: '请求失败,请稍后重试',
    warning: '该床位已存在占用记录',
    info: '提示:当天已经记录过一次',
  }
  push({ tone, text: messages[tone] })
}
</script>

<template>
  <main class="v2-shell">
    <!-- Hero -->
    <GlassPanel variant="card" tag="header" class="v2-hero">
      <template #header>
        <span class="label">智护银伴 · v2 / Phase 2</span>
      </template>
      <h1 class="display display-1 text-gradient">基础组件已落地</h1>
      <p class="body-l">
        本页展示 RFC §6.2 Phase 2 定义的 6 个基础原件 ——
        <Chip tone="accent">GlassPanel</Chip>
        <Chip tone="accent">Btn</Chip>
        <Chip tone="accent">Field</Chip>
        <Chip tone="accent">Chip</Chip>
        <Chip tone="accent">Dialog</Chip>
        <Chip tone="accent">Toast</Chip>
        ,均为对 <code>static/design/ui.css</code> 的零改动包装。
      </p>
      <dl class="v2-meta">
        <div><dt>构建时间</dt><dd>{{ buildTime }}</dd></div>
        <div><dt>/health</dt><dd>{{ health }}</dd></div>
      </dl>
    </GlassPanel>

    <!-- Buttons -->
    <GlassPanel class="v2-section">
      <template #header><h2 class="title-l">Btn</h2></template>
      <div class="row" style="flex-wrap: wrap; gap: var(--sp-2);">
        <Btn variant="primary">主按钮</Btn>
        <Btn variant="outline">Outline</Btn>
        <Btn variant="ghost">Ghost</Btn>
        <Btn variant="danger">删除</Btn>
        <Btn variant="primary" size="sm">Small</Btn>
        <Btn variant="primary" loading>提交中</Btn>
        <Btn variant="primary" disabled>禁用</Btn>
      </div>
    </GlassPanel>

    <!-- Fields -->
    <GlassPanel class="v2-section">
      <template #header><h2 class="title-l">Field</h2></template>
      <div class="grid-2">
        <Field
          v-model="inputText"
          label="姓名"
          required
          placeholder="如:张奶奶"
          hint="家属交接时使用的称呼即可"
        />
        <Field
          v-model="careLevel"
          label="护理等级"
          type="select"
        >
          <option value="care-1">一级 — 自理</option>
          <option value="care-2">二级 — 介助</option>
          <option value="care-3">三级 — 介护</option>
        </Field>
        <Field
          v-model="inputText"
          label="备注"
          type="textarea"
          placeholder="班组之间的额外提醒"
          :rows="3"
          style="grid-column: 1 / -1;"
        />
      </div>
    </GlassPanel>

    <!-- Chips -->
    <GlassPanel class="v2-section">
      <template #header><h2 class="title-l">Chip</h2></template>
      <div class="row" style="flex-wrap: wrap; gap: var(--sp-2);">
        <Chip>默认</Chip>
        <Chip tone="accent">护理重点</Chip>
        <Chip tone="success">已完成</Chip>
        <Chip tone="warning">待复核</Chip>
        <Chip tone="danger">高风险</Chip>
        <Chip tone="info">新</Chip>
      </div>
    </GlassPanel>

    <!-- Toast & Dialog -->
    <GlassPanel class="v2-section">
      <template #header><h2 class="title-l">Toast / Dialog</h2></template>
      <div class="row" style="flex-wrap: wrap; gap: var(--sp-2);">
        <Btn variant="primary" @click="fireToast('success')">触发 success toast</Btn>
        <Btn variant="outline" @click="fireToast('warning')">warning</Btn>
        <Btn variant="outline" @click="fireToast('error')">error</Btn>
        <Btn variant="ghost" @click="fireToast('info')">info</Btn>
        <Btn variant="primary" @click="dialogOpen = true">打开 Dialog</Btn>
      </div>
    </GlassPanel>

    <Dialog v-model="dialogOpen" title="确认操作">
      <p>此操作不可撤销,确定要继续吗?</p>
      <p class="body-s" style="margin-top: var(--sp-2);">
        Esc 关闭、点击遮罩关闭都已支持。
      </p>
      <template #actions>
        <Btn variant="ghost" @click="dialogOpen = false">取消</Btn>
        <Btn
          variant="danger"
          @click="() => { dialogOpen = false; push({ tone: 'success', text: '操作已确认' }) }"
        >
          确认
        </Btn>
      </template>
    </Dialog>

    <!-- 全局 Toast 容器 —— 整个应用挂一次即可 -->
    <Toast />
  </main>
</template>

<style scoped>
/* 仅页面布局:不引入新视觉语言。 */
.v2-shell {
  max-width: 960px;
  margin: 0 auto;
  padding: clamp(16px, 4vw, 40px);
  display: grid;
  gap: var(--sp-4, 16px);
}
.v2-hero h1 {
  margin: 0 0 var(--sp-2, 8px);
}
.v2-meta {
  display: grid;
  gap: 6px;
  margin-top: var(--sp-3, 12px);
  padding: var(--sp-3, 12px);
  border-radius: var(--r-s, 10px);
  background: rgba(15, 23, 42, 0.04);
  font: 400 var(--fz-xs, 12px) / 1.5 var(--font-mono, ui-monospace);
}
.v2-meta div {
  display: grid;
  grid-template-columns: 110px 1fr;
}
.v2-meta dt {
  color: var(--ink-3, rgba(15, 23, 42, 0.55));
}
.v2-section :deep(.vp-glass__header) {
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  padding-bottom: var(--sp-2, 8px);
}
</style>
