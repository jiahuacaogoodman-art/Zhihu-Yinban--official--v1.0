<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Btn, Field, GlassPanel } from '../components'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'

/**
 * Login — 登录页
 *
 * Phase 7 移动端深度适配 + 体验改进:
 *   1) 安全区填充(顶部 + 底部),避免 iOS 刘海/Home 指示条挡到内容
 *   2) Logo + 引导文案 + 大号输入框 + show/hide 密码切换
 *   3) 登录成功跳 /beds 而不是 / —— Landing 页对登录后用户没有信息密度,
 *      新用户登完看到首页会以为没登成功
 *   4) 支持 ?redirect=/path 跳回原页(从 401 抛回登录页时携带)
 *   5) iOS 软键盘弹出时,主动 scrollIntoView 让输入框保持可见
 */

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const { push: toast } = useToast()

const tokenInput = ref('')
const showToken = ref(false)
const loading = ref(false)
const tokenInputEl = ref<HTMLElement | null>(null)

const redirectTarget = computed(() => {
  const r = route.query.redirect
  if (typeof r === 'string' && r.startsWith('/') && !r.startsWith('//')) {
    return r
  }
  return '/beds'
})

async function handleLogin() {
  const t = tokenInput.value.trim()
  if (!t) return
  loading.value = true
  try {
    const res = await fetch('/api/beds', {
      headers: { 'X-Auth-Token': t },
    })
    if (res.status === 401) {
      toast({ tone: 'error', text: 'Token 无效，请检查后重试' })
      return
    }
    if (!res.ok && res.status !== 200) {
      toast({ tone: 'warning', text: `登录验证返回 ${res.status}，请检查后端是否启动` })
      // 仍允许登录(非 401 可能是后端模块未就绪),但提示一下
    }
    authStore.login(t)
    toast({ tone: 'success', text: '登录成功' })
    router.replace(redirectTarget.value)
  } catch {
    toast({ tone: 'error', text: '网络错误，请检查后端服务' })
  } finally {
    loading.value = false
  }
}

// 输入框聚焦时滚到视口中央，避免 iOS 软键盘把输入框挡住
async function onInputFocus() {
  await nextTick()
  setTimeout(() => {
    tokenInputEl.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 320) // 软键盘弹出动画后再滚
}
</script>

<template>
  <div class="login-page">
    <div class="login-bg" aria-hidden="true">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
    </div>

    <GlassPanel variant="card" class="login-card">
      <div class="login-brand">
        <div class="login-mark">♥</div>
        <div class="login-brand-text">
          <span class="title-l">智护银伴</span>
          <span class="meta">v2 · 管理端</span>
        </div>
      </div>

      <h1 class="login-title">欢迎回来</h1>
      <p class="login-sub">
        粘贴管理员发放的 <strong>API Token</strong> 即可登录
      </p>

      <form class="login-form" @submit.prevent="handleLogin">
        <div ref="tokenInputEl" class="login-field-wrap">
          <Field
            v-model="tokenInput"
            label="Auth Token"
            :type="showToken ? 'text' : 'password'"
            required
            placeholder="粘贴你的 AUTH_TOKEN"
            @focus="onInputFocus"
          />
          <button
            type="button"
            class="login-toggle"
            :aria-label="showToken ? '隐藏 Token' : '显示 Token'"
            @click="showToken = !showToken"
          >
            {{ showToken ? '🙈' : '👁' }}
          </button>
        </div>

        <Btn
          variant="primary"
          type="submit"
          :loading="loading"
          :disabled="!tokenInput.trim()"
          class="login-submit"
        >
          {{ loading ? '验证中…' : '登录' }}
        </Btn>
      </form>

      <details class="login-help">
        <summary>怎么获取 Token？</summary>
        <ol class="login-help-list">
          <li>
            <strong>首次部署</strong>：服务器执行 <code>./scripts/setup.sh</code> 后，
            终端会打印一行 <code>Admin Token: ...</code>，复制粘贴即可。
          </li>
          <li>
            <strong>已部署</strong>：管理员通过环境变量 <code>AUTH_TOKEN</code>
            或 <code>POST /api/auth/users</code> 创建 token。
          </li>
          <li>
            <strong>测试模式</strong>：把 <code>AUTH_TOKEN</code> 留空，后端会
            自动放行（仅本地开发用，禁止上线）。
          </li>
        </ol>
      </details>

      <div class="login-extra">
        <a href="/nurse" class="login-extra-link">
          <span>👩‍⚕️</span>
          <span>我是护工，进护工端 →</span>
        </a>
        <a href="/legacy" class="login-extra-link login-extra-link--muted">
          <span>🗂</span>
          <span>使用旧版界面 →</span>
        </a>
      </div>
    </GlassPanel>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: calc(env(safe-area-inset-top, 0px) + 24px) 16px
    calc(env(safe-area-inset-bottom, 0px) + 24px);
  position: relative;
  isolation: isolate;
}

.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: -1;
  overflow: hidden;
}
.login-bg .orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.4;
}
.login-bg .orb-1 {
  width: 360px;
  height: 360px;
  top: -120px;
  left: -80px;
  background: radial-gradient(circle at 30% 30%, #5eead4, #14b8a6 55%, transparent 72%);
}
.login-bg .orb-2 {
  width: 320px;
  height: 320px;
  bottom: -100px;
  right: -60px;
  background: radial-gradient(circle at 70% 30%, #c4b5fd, #818cf8 55%, transparent 72%);
}

.login-card {
  width: min(440px, 100%);
  display: grid;
  gap: var(--sp-3, 12px);
}
.login-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--sp-2, 8px);
}
.login-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--accent, #14b8a6), var(--accent-ink, #0f766e));
  color: #fff;
  font-size: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 6px 16px rgba(20, 184, 166, 0.35);
}
.login-brand-text {
  display: flex;
  flex-direction: column;
}

.login-title {
  margin: 0;
  font: 700 26px / 1.2 var(--font-display, serif);
  background: linear-gradient(135deg, #0f766e, #14b8a6 50%, #818cf8);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: -0.01em;
}
.login-sub {
  margin: 0;
  color: var(--ink-3);
  font: 400 14px / 1.5 var(--font-ui);
}
.login-sub strong {
  color: var(--accent-ink, #0f766e);
  font-weight: 600;
}

.login-form {
  display: grid;
  gap: var(--sp-3, 12px);
  margin-top: var(--sp-3, 12px);
}
.login-field-wrap {
  position: relative;
}
.login-toggle {
  position: absolute;
  right: 8px;
  top: 30px; /* 对齐 label 之下的输入框 */
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  color: var(--ink-3);
}
.login-toggle:hover {
  background: rgba(15, 23, 42, 0.05);
}

.login-submit {
  width: 100%;
  height: 48px;
  font-size: 15px;
}

.login-help {
  border-top: 1px dashed rgba(15, 23, 42, 0.08);
  padding-top: var(--sp-3, 12px);
  margin-top: var(--sp-2, 8px);
}
.login-help summary {
  cursor: pointer;
  font: 500 13px / 1.4 var(--font-ui);
  color: var(--accent-ink, #0f766e);
  padding: 4px 0;
}
.login-help-list {
  margin: 8px 0 0 18px;
  padding: 0;
  display: grid;
  gap: 6px;
  font: 400 12.5px / 1.65 var(--font-ui);
  color: var(--ink-3);
}
.login-help-list code {
  background: rgba(20, 184, 166, 0.1);
  color: var(--accent-ink, #0f766e);
  padding: 1px 5px;
  border-radius: 4px;
  font: 500 12px / 1 var(--font-mono);
}

.login-extra {
  display: grid;
  gap: 4px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  padding-top: var(--sp-3, 12px);
  margin-top: var(--sp-2, 8px);
}
.login-extra-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  text-decoration: none;
  font: 500 13px / 1.4 var(--font-ui);
  color: var(--accent-ink, #0f766e);
  background: rgba(20, 184, 166, 0.06);
  border: 1px solid rgba(20, 184, 166, 0.15);
  min-height: 44px;
}
.login-extra-link:hover {
  background: rgba(20, 184, 166, 0.12);
}
.login-extra-link--muted {
  color: var(--ink-3);
  background: rgba(15, 23, 42, 0.04);
  border-color: rgba(15, 23, 42, 0.08);
}
.login-extra-link--muted:hover {
  background: rgba(15, 23, 42, 0.08);
}

@media (max-width: 640px) {
  .login-page {
    padding-top: calc(env(safe-area-inset-top, 0px) + 32px);
  }
  .login-title {
    font-size: 24px;
  }
}
</style>
