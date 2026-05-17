<script setup lang="ts">
/**
 * Showcase — Phase 2 组件展示页(从 Phase 2 的 App.vue 搬过来)
 *
 * Phase 3 起 App.vue 变成了 layout + router-view;原来的 showcase 内容
 * 作为 /showcase 路由保留,方便团队随时查看设计系统样本。
 */
import { ref } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'

const dialogOpen = ref(false)
const inputText = ref('')
const { push } = useToast()

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
  <div class="showcase">
    <GlassPanel variant="card">
      <template #header><span class="label">组件展示 / Showcase</span></template>
      <h1 class="display display-2 text-gradient">6 个基础原件</h1>
    </GlassPanel>

    <GlassPanel>
      <template #header><h2 class="title-l">Btn</h2></template>
      <div class="row" style="flex-wrap: wrap; gap: var(--sp-2);">
        <Btn variant="primary">主按钮</Btn>
        <Btn variant="outline">Outline</Btn>
        <Btn variant="ghost">Ghost</Btn>
        <Btn variant="danger">删除</Btn>
        <Btn variant="primary" size="sm">Small</Btn>
        <Btn variant="primary" loading>提交中</Btn>
      </div>
    </GlassPanel>

    <GlassPanel>
      <template #header><h2 class="title-l">Field</h2></template>
      <div class="grid-2">
        <Field v-model="inputText" label="姓名" required placeholder="如:张奶奶" />
        <Field v-model="inputText" label="备注" type="textarea" :rows="2" />
      </div>
    </GlassPanel>

    <GlassPanel>
      <template #header><h2 class="title-l">Chip</h2></template>
      <div class="row" style="flex-wrap: wrap; gap: var(--sp-2);">
        <Chip>默认</Chip>
        <Chip tone="accent">强调</Chip>
        <Chip tone="success">成功</Chip>
        <Chip tone="warning">警告</Chip>
        <Chip tone="danger">危险</Chip>
        <Chip tone="info">信息</Chip>
      </div>
    </GlassPanel>

    <GlassPanel>
      <template #header><h2 class="title-l">Toast / Dialog</h2></template>
      <div class="row" style="flex-wrap: wrap; gap: var(--sp-2);">
        <Btn variant="primary" @click="fireToast('success')">success</Btn>
        <Btn variant="outline" @click="fireToast('warning')">warning</Btn>
        <Btn variant="outline" @click="fireToast('error')">error</Btn>
        <Btn variant="ghost" @click="dialogOpen = true">打开 Dialog</Btn>
      </div>
    </GlassPanel>

    <Dialog v-model="dialogOpen" title="确认操作">
      <p>此操作不可撤销,确定要继续吗?</p>
      <template #actions>
        <Btn variant="ghost" @click="dialogOpen = false">取消</Btn>
        <Btn variant="danger" @click="dialogOpen = false">确认</Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.showcase {
  display: grid;
  gap: var(--sp-4, 16px);
}
</style>
