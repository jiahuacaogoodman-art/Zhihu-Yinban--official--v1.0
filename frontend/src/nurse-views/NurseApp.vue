<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { NetworkBanner, Toast } from '../components'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'
import { useScrollLock } from '../composables/useScrollLock'
import { useViewport } from '../composables/useViewport'
import { useNetworkStatus } from '../composables/useNetworkStatus'
import { useSwipeBack } from '../composables/useSwipeBack'

/**
 * NurseApp — 护工端根布局(Phase 7 移动端深度适配)
 *
 * 与管理端不同:
 *   - 移动端优先: 顶部 appbar(深色) + 主内容区 + 底部 tab(老人 / 任务 / 我)
 *   - 安全区填充(viewport-fit=cover 已在 nurse.html 设置)
 *   - 顶栏:汉堡(打开关于面板) | 当前页标题 | 跳管理端
 *   - 底部 tab:老人列表 / 任务卡(=当前选中老人详情) / 我的(退出登录 + 关于)
 *
 * "我的"页用一个简单的 sheet (right drawer) 实现,不开新路由 —— 护工端只两条
 * 实际业务路由,加路由意义不大。
 */

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { push: toast } = useToast()

const moreOpen = ref(false)
useScrollLock(moreOpen)

// ── 软键盘 / 视口监听 ──
const { keyboardOpen, keyboardHeight } = useViewport()
watch(
  keyboardOpen,
  (v) => {
    if (typeof document === 'undefined') return
    document.body.classList.toggle('kb-open', !!v)
  },
  { immediate: true },
)
watch(
  keyboardHeight,
  (h) => {
    if (typeof document === 'undefined') return
    document.documentElement.style.setProperty('--v2-keyboard-h', `${h}px`)
  },
  { immediate: true },
)

// ── 离线状态 ──
const { offline } = useNetworkStatus()
watch(
  offline,
  (v) => {
    if (typeof document === 'undefined') return
    document.body.classList.toggle('netbanner-on', !!v)
  },
  { immediate: true },
)

// ── 边缘右滑返回:仅在患者详情页生效(从详情回老人列表) ──
const swipeBackEnabled = computed(() => route.name === 'nurse-patient')
useSwipeBack(
  () => {
    if (moreOpen.value) {
      moreOpen.value = false
      return
    }
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back()
    } else {
      router.push('/')
    }
  },
  { enabled: swipeBackEnabled },
)

// ── ESC 关 sheet ──
function onGlobalKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && moreOpen.value) {
    moreOpen.value = false
  }
}
onMounted(() => {
  if (typeof document === 'undefined') return
  document.addEventListener('keydown', onGlobalKey)
})
onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.removeEventListener('keydown', onGlobalKey)
  document.body.classList.remove('kb-open', 'netbanner-on')
})

// 当前页标题
const currentTitle = computed(() => {
  const t = route.meta?.title as string | undefined
  return t ?? '护工端'
})

// 当前是否在"患者详情"页(用于底部 tab 的"任务"高亮)
const isOnPatient = computed(() => route.name === 'nurse-patient')

// 当前选中患者 id(从路由 params 拿,用于"任务"tab 跳回)
const selectedPatientId = computed(() => {
  if (route.name === 'nurse-patient') {
    const id = route.params.id
    return typeof id === 'string' ? id : null
  }
  return null
})

watch(
  () => route.fullPath,
  () => {
    moreOpen.value = false
  },
)

function handleLogout() {
  auth.logout()
  toast({ tone: 'success', text: '已退出登录' })
  // 护工端登出后跳管理端登录页
  window.location.href = '/login'
}

// 底部 tab 点击"任务"时,如果当前没有选中患者,提示先选老人
function goToTask() {
  if (selectedPatientId.value) {
    router.push(`/patient/${selectedPatientId.value}`)
  } else {
    toast({ tone: 'info', text: '请先在"老人"列表选择一位老人' })
    router.push('/')
  }
}
</script>

<template>
  <div class="nurse-layout">
    <!-- ───── 顶部 appbar ───── -->
    <header class="nurse-appbar">
      <div class="nurse-brand">
        <span class="nurse-mark">♥</span>
        <span class="nurse-name">智护银伴</span>
        <span class="nurse-tag">护工端</span>
      </div>
      <h1 class="nurse-title" v-if="currentTitle">{{ currentTitle }}</h1>
      <a href="/" class="nurse-link" aria-label="切换到管理端">管理端</a>
    </header>

    <!-- ───── 主内容 ───── -->
    <main class="nurse-main">
      <router-view />
    </main>

    <!-- ───── 底部 tab ───── -->
    <nav class="nurse-bottom" aria-label="主要功能">
      <RouterLink
        to="/"
        class="nb-item"
        active-class="nb-item--active"
        :exact-active-class="'nb-item--active'"
      >
        <span class="ic">👥</span>
        <span class="lb">老人</span>
      </RouterLink>
      <button
        type="button"
        class="nb-item"
        :class="{ 'nb-item--active': isOnPatient }"
        :disabled="!selectedPatientId && !isOnPatient"
        @click="goToTask"
      >
        <span class="ic">📋</span>
        <span class="lb">任务</span>
      </button>
      <button
        type="button"
        class="nb-item"
        :class="{ 'nb-item--active': moreOpen }"
        @click="moreOpen = true"
      >
        <span class="ic">👤</span>
        <span class="lb">我的</span>
      </button>
    </nav>

    <!-- ───── "我的"sheet ───── -->
    <Teleport to="body">
      <div
        v-if="moreOpen"
        class="nurse-scrim"
        @click="moreOpen = false"
      ></div>
      <div
        v-if="moreOpen"
        class="nurse-sheet"
        role="dialog"
        aria-modal="true"
      >
        <div class="nurse-sheet-handle" aria-hidden="true"></div>
        <h2 class="nurse-sheet-title">个人</h2>

        <div class="nurse-sheet-section">
          <div class="nurse-sheet-row">
            <span class="ic">🪪</span>
            <span class="lb">登录状态</span>
            <span class="val">{{ auth.isAuthenticated ? '已登录' : '未登录' }}</span>
          </div>
        </div>

        <div class="nurse-sheet-section">
          <a href="/" class="nurse-sheet-action">
            <span class="ic">🖥</span>
            <span>切换到管理端</span>
            <span class="arrow">→</span>
          </a>
          <a href="/legacy" class="nurse-sheet-action">
            <span class="ic">🗂</span>
            <span>使用旧版界面</span>
            <span class="arrow">→</span>
          </a>
        </div>

        <div class="nurse-sheet-section">
          <button
            v-if="auth.isAuthenticated"
            type="button"
            class="nurse-sheet-action nurse-sheet-action--danger"
            @click="handleLogout"
          >
            <span class="ic">⏻</span>
            <span>退出登录</span>
          </button>
        </div>

        <button
          type="button"
          class="nurse-sheet-close"
          @click="moreOpen = false"
        >
          关闭
        </button>
      </div>
    </Teleport>

    <NetworkBanner />
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

.nurse-appbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: calc(env(safe-area-inset-top, 0px) + 10px) 12px 10px;
  min-height: calc(48px + env(safe-area-inset-top, 0px));
  background: rgba(11, 18, 32, 0.88);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
  color: #fff;
}

.nurse-brand {
  display: flex;
  align-items: center;
  gap: 6px;
  font: 600 14px/1 var(--font-ui);
  flex-shrink: 0;
  min-width: 0;
}
.nurse-mark {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: linear-gradient(135deg, var(--accent), var(--accent-ink));
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
}
.nurse-tag {
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 4px;
  background: rgba(94, 234, 212, 0.18);
  color: #5eead4;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}
.nurse-title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font: 500 14px/1.2 var(--font-ui);
  color: rgba(255, 255, 255, 0.85);
  text-align: center;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nurse-link {
  flex-shrink: 0;
  height: 32px;
  padding: 0 10px;
  border-radius: 7px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  font: 500 12px/1 var(--font-ui);
  white-space: nowrap;
}
.nurse-link:active {
  background: rgba(255, 255, 255, 0.18);
}

.nurse-main {
  flex: 1;
  padding: 12px 12px calc(env(safe-area-inset-bottom, 0px) + 76px);
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

@media (max-width: 640px) {
  .nurse-appbar {
    gap: 8px;
    padding: calc(env(safe-area-inset-top, 0px) + 8px) 10px 8px;
    min-height: calc(44px + env(safe-area-inset-top, 0px));
  }
  .nurse-name {
    /* 极窄屏隐藏品牌字，让标题居中显得不挤 */
    display: none;
  }
  .nurse-tag {
    display: none;
  }
  .nurse-title {
    font-size: 13px;
  }
  .nurse-link {
    height: 30px;
    padding: 0 8px;
    font-size: 11px;
  }
  .nurse-main {
    padding: 10px 10px calc(env(safe-area-inset-bottom, 0px) + 72px);
  }
}

@media (max-width: 380px) {
  .nurse-appbar {
    gap: 6px;
    padding: calc(env(safe-area-inset-top, 0px) + 6px) 8px 6px;
    min-height: calc(40px + env(safe-area-inset-top, 0px));
  }
  .nurse-mark {
    width: 24px;
    height: 24px;
    font-size: 11px;
  }
  .nurse-title {
    font-size: 12px;
  }
  .nurse-link {
    height: 28px;
    padding: 0 6px;
    font-size: 10px;
    border-radius: 6px;
  }
  .nurse-main {
    padding: 8px 8px calc(env(safe-area-inset-bottom, 0px) + 68px);
  }
}
</style>

<style>
/* ─── 全局样式：底部 tab + sheet (Teleport 出去的元素) ─── */

.nurse-bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 25;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  padding: 6px 4px calc(env(safe-area-inset-bottom, 0px) + 4px);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(22px) saturate(180%);
  -webkit-backdrop-filter: blur(22px) saturate(180%);
  border-top: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 -6px 22px rgba(15, 23, 42, 0.06);
}
.nb-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 4px 4px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: var(--ink-3, #475569);
  text-decoration: none;
  font: 500 11px/1.2 var(--font-ui);
  cursor: pointer;
  min-height: 46px;
}
.nb-item:disabled {
  color: var(--ink-5, #cbd5e1);
  cursor: not-allowed;
}
.nb-item .ic {
  font-size: 22px;
  line-height: 1;
}
.nb-item:active:not(:disabled) {
  background: rgba(20, 184, 166, 0.08);
}
.nb-item--active {
  color: var(--accent-ink, #0f766e);
}

@media (max-width: 380px) {
  .nurse-bottom {
    padding: 4px 2px calc(env(safe-area-inset-bottom, 0px) + 2px);
  }
  .nb-item {
    min-height: 42px;
    font-size: 10px;
  }
  .nb-item .ic {
    font-size: 20px;
  }
}

/* ─── 我的 sheet ─── */
.nurse-scrim {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(11, 18, 32, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  animation: nurse-fade-in 200ms ease;
}
@keyframes nurse-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.nurse-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 60;
  background: #fff;
  border-radius: 20px 20px 0 0;
  box-shadow: 0 -16px 48px rgba(15, 23, 42, 0.20);
  padding: 8px 16px calc(env(safe-area-inset-bottom, 0px) + 24px);
  animation: nurse-sheet-up 280ms cubic-bezier(0.34, 1.56, 0.64, 1);
  max-height: 88dvh;
  overflow-y: auto;
}
@keyframes nurse-sheet-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.nurse-sheet-handle {
  width: 40px;
  height: 4px;
  margin: 4px auto 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.18);
}
.nurse-sheet-title {
  margin: 0 0 12px;
  font: 600 18px/1.3 var(--font-ui);
}
.nurse-sheet-section {
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  padding: 8px 0;
  display: grid;
  gap: 2px;
}
.nurse-sheet-section:first-of-type { border-top: none; }
.nurse-sheet-row,
.nurse-sheet-action {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  border-radius: 10px;
  text-decoration: none;
  background: transparent;
  border: none;
  cursor: pointer;
  font: 500 15px/1.4 var(--font-ui);
  color: var(--ink-1);
  width: 100%;
  text-align: left;
  min-height: 48px;
}
.nurse-sheet-row {
  cursor: default;
}
.nurse-sheet-row .val {
  margin-left: auto;
  color: var(--accent-ink, #0f766e);
  font-weight: 600;
}
.nurse-sheet-action:active {
  background: rgba(15, 23, 42, 0.05);
}
.nurse-sheet-action .arrow {
  margin-left: auto;
  color: var(--ink-4);
}
.nurse-sheet-action--danger {
  color: var(--red, #dc2626);
}
.nurse-sheet-action--danger:active {
  background: rgba(239, 68, 68, 0.08);
}
.nurse-sheet-action .ic {
  font-size: 18px;
  width: 28px;
  text-align: center;
}

.nurse-sheet-close {
  margin: 16px auto 0;
  display: block;
  height: 44px;
  padding: 0 32px;
  border-radius: 22px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(15, 23, 42, 0.04);
  color: var(--ink-2);
  font: 500 14px/1 var(--font-ui);
  cursor: pointer;
}
</style>
