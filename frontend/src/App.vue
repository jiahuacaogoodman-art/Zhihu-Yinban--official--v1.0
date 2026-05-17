<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Toast } from './components'

/**
 * App.vue — 根布局
 *
 * 结构:侧栏导航 + 主内容区(router-view)。
 * 当路由 meta.fullBleed = true(如 Landing / Login)时,
 *   隐藏侧栏 + 主内容区取消 max-width 限制,让动效可以铺满。
 */

const route = useRoute()
const fullBleed = computed(() => route.meta.fullBleed === true)
</script>

<template>
  <div class="v2-layout" :class="{ 'v2-layout--full': fullBleed }">
    <aside v-if="!fullBleed" class="v2-sidebar">
      <div class="v2-sidebar-brand">
        <span class="title-s">智护银伴</span>
        <span class="meta">v2</span>
      </div>
      <nav class="v2-nav">
        <router-link to="/" class="v2-nav-item" active-class="v2-nav-active">
          首页
        </router-link>
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
        <a href="/legacy" class="v2-nav-item" style="color: var(--ink-4);">旧版入口 →</a>
      </div>
    </aside>

    <main class="v2-main" :class="{ 'v2-main--full': fullBleed }">
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
.v2-layout--full {
  grid-template-columns: 1fr;
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
.v2-main--full {
  padding: 0;
  max-width: none;
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
