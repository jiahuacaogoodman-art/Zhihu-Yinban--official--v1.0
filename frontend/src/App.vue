<script setup lang="ts">
import { Toast } from './components'

/**
 * App.vue — Phase 3 起的根布局
 *
 * 结构:侧栏导航 + 主内容区(router-view)。
 * 全局 Toast 容器挂在这里,整个应用复用。
 *
 * 侧栏暂时极简(只有几个链接);Phase 4 全量迁移时丰富。
 */
</script>

<template>
  <div class="v2-layout">
    <aside class="v2-sidebar">
      <div class="v2-sidebar-brand">
        <span class="title-s">智护银伴</span>
        <span class="meta">v2</span>
      </div>
      <nav class="v2-nav">
        <router-link to="/beds" class="v2-nav-item" active-class="v2-nav-active">
          床位管理
        </router-link>
        <router-link to="/ehr" class="v2-nav-item" active-class="v2-nav-active">
          患者档案
        </router-link>
        <router-link to="/handovers" class="v2-nav-item" active-class="v2-nav-active">
          交接班
        </router-link>
        <router-link to="/incidents" class="v2-nav-item" active-class="v2-nav-active">
          异常事件
        </router-link>
        <router-link to="/care-records" class="v2-nav-item" active-class="v2-nav-active">
          护理记录
        </router-link>
        <router-link to="/showcase" class="v2-nav-item" active-class="v2-nav-active">
          组件展示
        </router-link>
      </nav>
      <div class="v2-sidebar-footer">
        <a href="/" class="v2-nav-item" style="color: var(--ink-4);">返回旧版 →</a>
      </div>
    </aside>

    <main class="v2-main">
      <router-view />
    </main>

    <Toast />
  </div>
</template>

<style scoped>
.v2-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}

.v2-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: var(--sp-4, 16px);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
  border-right: 1px solid rgba(15, 23, 42, 0.06);
}

.v2-sidebar-brand {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2, 8px);
  margin-bottom: var(--sp-4, 16px);
  padding-bottom: var(--sp-3, 12px);
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.v2-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.v2-nav-item {
  display: block;
  padding: var(--sp-2, 8px) var(--sp-3, 12px);
  border-radius: var(--r-s, 10px);
  font: 500 var(--fz-sm, 13px) / 1.4 var(--font-ui, sans-serif);
  color: var(--ink-2, rgba(15, 23, 42, 0.75));
  text-decoration: none;
  transition: background var(--dur-fast, 120ms) var(--ease, ease);
}
.v2-nav-item:hover {
  background: rgba(15, 23, 42, 0.04);
}
.v2-nav-active {
  background: rgba(20, 184, 166, 0.1);
  color: var(--accent-ink, #0f766e);
  font-weight: 600;
}

.v2-sidebar-footer {
  margin-top: auto;
  padding-top: var(--sp-3, 12px);
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.v2-main {
  padding: var(--sp-5, 20px);
  max-width: 1200px;
  width: 100%;
}

/* 移动端:隐藏侧栏,全宽 */
@media (max-width: 768px) {
  .v2-layout {
    grid-template-columns: 1fr;
  }
  .v2-sidebar {
    display: none;
  }
}
</style>
