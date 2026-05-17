<script setup lang="ts">
import { Toast } from '../components'

/**
 * NurseApp — 护工端根布局
 *
 * 与管理端不同:
 *   - 无侧栏(移动端优先,全屏使用)
 *   - 顶栏:品牌 + 当前标题 + 跳管理端按钮
 *   - 底栏:移动端 tab bar(Phase 5 仅保留回退按钮)
 */
</script>

<template>
  <div class="nurse-layout">
    <header class="nurse-header">
      <div class="nurse-brand">
        <span class="nurse-mark">♥</span>
        <span class="title-s">智护银伴</span>
        <span class="meta">护工端</span>
      </div>
      <a href="/" class="btn btn-ghost btn-sm" style="margin-left: auto;">
        管理端
      </a>
    </header>

    <main class="nurse-main">
      <router-view />
    </main>

    <Toast />
  </div>
</template>

<style scoped>
.nurse-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
}

.nurse-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: var(--sp-3, 12px);
  padding: 0 var(--sp-4, 16px);
  height: 56px;
  background: rgba(11, 18, 32, 0.88);
  backdrop-filter: blur(14px) saturate(150%);
  -webkit-backdrop-filter: blur(14px) saturate(150%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  color: #fff;
}

.nurse-brand {
  display: flex;
  align-items: center;
  gap: var(--sp-2, 8px);
}

.nurse-mark {
  width: 32px;
  height: 32px;
  border-radius: var(--r-s, 10px);
  background: linear-gradient(135deg, var(--accent, #14b8a6), var(--accent-ink, #0f766e));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #fff;
}

.nurse-main {
  flex: 1;
  padding: var(--sp-4, 16px);
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

@media (max-width: 640px) {
  .nurse-main {
    padding: var(--sp-3, 12px);
  }
}
</style>
