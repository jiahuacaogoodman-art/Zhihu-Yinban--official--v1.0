<script setup lang="ts">
import { ref, onMounted } from 'vue'

/**
 * Phase 1 占位页 —— 它存在的唯一目的是证明 RFC §6.1 的 "Phase 1 Done":
 *   "/v2/ 能打开一个写着 Hello v2 的页面;CI 上 npm run build 通过;
 *    Dockerfile 能正常构建镜像。"
 *
 * 不做的事(留给后续 phase):
 *   - 不接入 router / Pinia / api client
 *   - 不引 glass.css / ui.css 的业务组件
 *   - 不消费 /api/* (但探一下 /health 用来证明同源访问没问题)
 */

const buildTime = __BUILD_TIME__
const health = ref<string>('checking...')

onMounted(async () => {
  try {
    const res = await fetch('/health', { cache: 'no-store' })
    if (!res.ok) {
      health.value = `unreachable (${res.status})`
      return
    }
    const data = await res.json()
    health.value = data.status ?? 'unknown'
  } catch (e) {
    health.value = 'unreachable'
  }
})
</script>

<template>
  <main class="phase1-shell">
    <section class="phase1-card">
      <p class="phase1-eyebrow">智护银伴 · v2</p>
      <h1 class="phase1-title">Hello v2</h1>
      <p class="phase1-lede">
        前端重构 Phase 1 占位页 — 基于 Vite + Vue 3 的骨架已就绪。
      </p>
      <dl class="phase1-meta">
        <div>
          <dt>路线图</dt>
          <dd>
            <a href="/static/../docs/FRONTEND_REFACTOR_RFC.md">FRONTEND_REFACTOR_RFC.md</a>
            (PR #8 已合并)
          </dd>
        </div>
        <div>
          <dt>当前阶段</dt>
          <dd>Phase 1 / 6 — Vite 骨架 + 占位页 + CI</dd>
        </div>
        <div>
          <dt>下一阶段</dt>
          <dd>Phase 2 — 设计系统迁移(6 个基础组件)</dd>
        </div>
        <div>
          <dt>构建时间</dt>
          <dd>{{ buildTime }}</dd>
        </div>
        <div>
          <dt>/health</dt>
          <dd>{{ health }}</dd>
        </div>
      </dl>
      <p class="phase1-hint">
        旧版仍在
        <a href="/">/</a> · <a href="/nurse">/nurse</a> · <a href="/billing">/billing</a>
        ,Phase 6 之前永久保留作为 fallback。
      </p>
    </section>
  </main>
</template>
